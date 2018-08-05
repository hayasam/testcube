import re
from datetime import datetime, timezone, timedelta

from django.db.models import Q
from rest_framework import viewsets
from rest_framework.decorators import detail_route, list_route
from rest_framework.pagination import LimitOffsetPagination
from rest_framework.permissions import IsAdminUser
from rest_framework.response import Response
from tagging.models import Tag

from testcube.settings import logger
from .filters import *
from .serializers import *
from ...utils import get_auto_cleanup_run_days, cleanup_run_media


def info_view(self, serializer_class):
    self.serializer_class = serializer_class
    instance = self.get_object()
    serializer = self.get_serializer(instance)
    return Response(serializer.data)


def list_view(self):
    self.pagination_class = LimitOffsetPagination

    queryset = self.filter_queryset(self.get_queryset())
    page = self.paginate_queryset(queryset)

    if page is not None:
        serializer = self.get_serializer(page, many=True)
        return self.get_paginated_response(serializer.data)

    serializer = self.get_serializer(queryset, many=True)
    return Response(serializer.data)


class TeamViewSet(viewsets.ModelViewSet):
    queryset = Team.objects.all()
    serializer_class = TeamSerializer
    filter_fields = ('name', 'owner')
    search_fields = filter_fields

    @list_route()
    def recent(self, request):
        """get recent teams"""
        self.queryset = Team.objects.order_by('name').all()
        self.serializer_class = TeamListSerializer
        return list_view(self)


class ProductViewSet(viewsets.ModelViewSet):
    queryset = Product.objects.all()
    serializer_class = ProductSerializer
    filter_fields = ('name', 'owner', 'version', 'team')
    search_fields = ('name', 'owner', 'version')

    @list_route()
    def recent(self, request):
        """get recent teams"""
        self.queryset = Product.objects.order_by('name').all()
        self.serializer_class = ProductListSerializer
        return list_view(self)

    @detail_route(methods=['get'])
    def tags(self, request, pk=None):
        product = self.get_object()
        case_query = TestCase.objects.filter(product_id=product.id).all()
        tags = Tag.objects.usage_for_queryset(case_query)
        tags = [t.name for t in tags]
        return Response(data=tags)


class ConfigurationViewSet(viewsets.ModelViewSet):
    permission_classes = [IsAdminUser]
    queryset = Configuration.objects.all()
    serializer_class = ConfigurationSerializer
    filter_fields = ('key', 'value')
    search_fields = filter_fields


class TestClientViewSet(viewsets.ModelViewSet):
    queryset = TestClient.objects.all()
    serializer_class = TestClientSerializer
    filter_fields = ('name', 'ip', 'platform', 'owner')
    search_fields = filter_fields


class TestRunViewSet(viewsets.ModelViewSet):
    queryset = TestRun.objects.all()
    serializer_class = TestRunSerializer
    filter_fields = ('name', 'state', 'status', 'owner', 'product')
    search_fields = ('name', 'owner')

    @detail_route(methods=['get'])
    def info(self, request, pk=None):
        return info_view(self, TestRunDetailSerializer)

    @detail_route(methods=['get'])
    def tags(self, request, pk=None):
        run = self.get_object()
        case_query = TestCase.objects.filter(results__test_run_id=run.id).all()
        tags = Tag.objects.usage_for_queryset(case_query, counts=True)

        tags = [(t.name, t.count) for t in tags]
        tags = sorted(tags, key=lambda tag: -tag[1])
        no_tag_tc = len([tc for tc in case_query if not tc.tags])

        if no_tag_tc:
            tags.append(('no_tags', no_tag_tc))

        return Response(data=tags)

    @list_route()
    def recent(self, request):
        """get recent runs, in run list view"""
        self.serializer_class = TestRunListSerializer
        self.filter_class = TestRunFilter
        return list_view(self)

    @list_route()
    def clear(self, request):
        """clear dead runs, will be called async when user visit run list."""
        pending_runs = TestRun.objects.filter(state__lt=2)  # not ready, starting, running
        fixed = []

        for run in pending_runs:
            delta = datetime.now(timezone.utc) - run.start_time
            if delta.days > 1 and run.state < 2:
                logger.info('abort run: {}'.format(run.id))
                run.state, run.status = 2, 1  # abort, failed
                run.save()
                fixed.append(run.id)

        bad_runs = TestRun.objects.filter(results=None)  # run without results > 2 days
        for run in bad_runs:
            if (datetime.now(tz=timezone.utc) - run.start_time).days >= 2:
                logger.info('delete run: {}'.format(run.id))
                fixed.append(run.id)
                run.delete()

        return Response(data=fixed)

    @list_route()
    def cleanup(self, request):
        """cleanup runs = delete old runs via config value."""
        if 'days' in request.GET:
            days = int(request.GET.get('days'))
        else:
            days = get_auto_cleanup_run_days()

        if days <= 0:
            return Response(data=[])

        logger.info('clean up runs before {} days'.format(days))
        time_threshold = datetime.now(tz=timezone.utc) - timedelta(days=days)
        pending_runs = TestRun.objects.filter(start_time__lt=time_threshold)
        fixed = []

        for run in pending_runs:
            logger.info('delete old run: {}'.format(run.id))
            cleanup_run_media(run.id)
            fixed.append(run.id)
            run.delete()

        return Response(data=fixed)

    @detail_route(methods=['get'])
    def history(self, request, pk=None):
        """get run history, will be used in run detail page."""
        instance = self.get_object()
        self.filter_fields = ()
        self.queryset = TestRun.objects.filter(name=instance.name, product=instance.product)
        self.serializer_class = TestRunListSerializer
        return list_view(self)


class TestCaseViewSet(viewsets.ModelViewSet):
    queryset = TestCase.objects.all()
    serializer_class = TestCaseSerializer
    filter_fields = ('name', 'full_name', 'keyword', 'priority', 'owner', 'product')
    search_fields = ('name', 'full_name', 'keyword')

    @detail_route(methods=['get'])
    def info(self, request, pk=None):
        """query result info, use for result detail page."""
        return info_view(self, TestCaseDetailSerializer)

    @detail_route(methods=['get', 'post'])
    def tags(self, request, pk=None):
        """query result tags"""
        from tagging.models import Tag
        instance = self.get_object()

        if request.method == 'POST':
            method = request.POST.get('method', 'add')
            tag_name = request.POST.get('tags', '').lower()

            if not bool(re.fullmatch('[ _\w-]+', tag_name)):
                return Response({'error': 'bad tag name!'}, status=400)

            if method == 'add':
                Tag.objects.add_tag(instance, tag_name)

            elif method == 'remove':
                tags = [t.name for t in instance.tags if t.name != tag_name]
                instance.tags = ','.join(tags)

        tags = [t.name for t in instance.tags]
        return Response(data=tags)

    @list_route()
    def recent(self, request):
        """get recent testcase, use for test case page."""
        self.serializer_class = TestCaseListSerializer
        self.filter_class = TestCaseFilter
        return list_view(self)

    @detail_route(methods=['get'])
    def history(self, request, pk=None):
        """get test case history, use in test case view or result detail view."""
        instance = self.get_object()
        self.filter_fields = ()
        self.queryset = TestResult.objects.filter(testcase__id=instance.id)
        self.serializer_class = TestResultHistorySerializer
        return list_view(self)


class TestResultViewSet(viewsets.ModelViewSet):
    queryset = TestResult.objects.all()
    serializer_class = TestResultSerializer
    filter_fields = ('outcome', 'assigned_to')
    search_fields = filter_fields

    @detail_route(methods=['get'])
    def info(self, request, pk=None):
        """query result info, use for result detail page."""
        return info_view(self, TestResultDetailSerializer)

    @detail_route(methods=['get'])
    def files(self, request, pk=None):
        """query result files, use for result detail page."""
        return info_view(self, TestResultFilesSerializer)

    @detail_route(methods=['get'])
    def resets(self, request, pk=None):
        """query result reset history, use for result detail page."""
        return info_view(self, TestResultResetHistorySerializer)

    @list_route()
    def recent(self, request):
        """get recent runs, in run list view"""
        self.serializer_class = TestResultListSerializer

        keyword = request.GET.get('search', None)
        if keyword:
            self.queryset = TestResult.objects.filter(Q(testcase__name__icontains=keyword) |
                                                      Q(error__message__icontains=keyword))

        self.search_fields = ()
        return list_view(self)


class IssueViewSet(viewsets.ModelViewSet):
    queryset = Issue.objects.all()
    serializer_class = IssueSerializer
    filter_fields = ('name', 'summary', 'created_by', 'assigned_to', 'status')
    search_fields = filter_fields


class ResultAnalysisViewSet(viewsets.ModelViewSet):
    queryset = ResultAnalysis.objects.all()
    serializer_class = ResultAnalysisSerializer
    filter_fields = ('by', 'reason', 'description')
    search_fields = filter_fields


class ResultErrorViewSet(viewsets.ModelViewSet):
    queryset = ResultError.objects.all()
    serializer_class = ResultErrorSerializer
    filter_fields = ('exception_type', 'message', 'stacktrace', 'stdout')
    search_fields = filter_fields


class ObjectSourceViewSet(viewsets.ModelViewSet):
    queryset = ObjectSource.objects.all()
    serializer_class = ObjectSourceSerializer
    filter_fields = ()
    search_fields = filter_fields


class ResultFileViewSet(viewsets.ModelViewSet):
    queryset = ResultFile.objects.all()
    serializer_class = ResultFileSerializer
    filter_fields = ()
    search_fields = filter_fields


class ResetResultViewSet(viewsets.ModelViewSet):
    queryset = ResetResult.objects.all()
    serializer_class = ResetResultSerializer
    filter_fields = ('id',)
    search_fields = filter_fields

    @list_route()
    def clear(self, request):
        """clear dead results and reset tasks, will be called async when user visit run detail page."""
        pending_resets = ResetResult.objects.filter(reset_status__lt=2)  # none, in progress
        fixed = []

        for result in pending_resets:
            delta = datetime.now(timezone.utc) - result.reset_on
            if delta.days > 1:
                logger.info('abort reset result: {}'.format(result.id))
                result.outcome, result.reset_status = 1, 3  # failed, failed
                result.stdout = 'Reset task timeout.'
                result.save()
                fixed.append(result.id)

        return Response(data=fixed)

    @detail_route(methods=['get', 'post'])
    def handler(self, request, pk=None):
        """
        Handle single reset result.
        1. update current reset result with provided info.
        2. create error object if required.
        3. update original result with latest outcome.
        4. update original run to passed if all result passed
        """

        if request.method == 'GET':
            return self.retrieve(self, request, pk=pk)

        current_reset = self.get_object()
        assert isinstance(current_reset, ResetResult)
        required_fields = ['outcome', 'duration', 'run_on', 'test_client', 'stdout']
        optional_field = ['exception_type', 'message', 'stacktrace', 'stdout', 'stderr']

        try:
            for f in required_fields:
                value = self.request.POST.get(f)

                if f == 'stdout' and not value:
                    value = 'Nothing in output.'

                if value is None:
                    raise ValueError('Field "{}" is required!'.format(f))

                if f == 'duration':
                    current_reset.duration = timedelta(seconds=float(value))

                elif f == 'test_client':
                    current_reset.test_client = TestClient.objects.get(id=int(value))

                else:
                    setattr(current_reset, f, value)

            has_error = self.request.POST.get(optional_field[0], None)

            if has_error:
                error = ResultError() if not current_reset.error else current_reset.error

                for f in optional_field:
                    value = self.request.POST.get(f, None)
                    setattr(error, f, value)

                error.save()
                current_reset.error = error

            # update original result outcome to current reset outcome
            current_reset.reset_status = 2  # done
            current_reset.save()
            current_reset.origin_result.outcome = current_reset.outcome
            current_reset.origin_result.save()

            # update original run status to passed if no failed result
            run = current_reset.origin_result.test_run
            if run.result_failed() == 0:
                run.status = 0  # passed
                run.save()

            return Response(data={'message': 'Result has been saved.'})

        except Exception as e:
            logger.exception('Failed to handle reset result: {}'.format(pk))
            current_reset.reset_status = 3  # failed
            current_reset.save()
            return Response(data={'message': str(e.args)}, status=400)
