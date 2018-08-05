"""testcube URL Configuration

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/1.11/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  url(r'^$', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  url(r'^$', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.conf.urls import url, include
    2. Add a URL to urlpatterns:  url(r'^blog/', include('blog.urls'))
"""
from django.conf import settings
from django.conf.urls import url, include
from django.conf.urls.static import static
from django.contrib import admin
from rest_framework import routers

from .core import views
from .core.api import api_registration as core_api_registration
from .core.api import client_auth
from .runner.api import api_registration as runner_api_registration
from .users import views as user_views

admin.site.site_header = 'TestCube Administration'
admin.site.site_title = admin.site.site_header

router = routers.DefaultRouter()
core_api_registration(router)
runner_api_registration(router)

urlpatterns = [
    url(r'^admin/', admin.site.urls),

    url(r'^api/', include(router.urls), name='api'),
    url(r'^api-auth/', include('rest_framework.urls', namespace='rest_framework')),
    url(r'^client-register', client_auth.register, name='client_register'),

    url('^signin$', user_views.signin, name='signin'),
    url('^signup$', user_views.signup, name='signup'),
    url('^signout$', user_views.signout, name='signout'),
    url('^reset$', user_views.reset_password, name='reset_password'),
    url('^profile$', user_views.user_profile, name='user_profile'),

    url(r'^$', views.index, name='index'),
    url(r'^welcome$', views.welcome, name='welcome'),
    url(r'^docs/(?P<name>.+)$', views.document, name='docs'),

    url(r'^runs$', views.runs, name='runs'),
    url(r'^runs/(\d+)$', views.run_detail, name='run_detail'),
    url(r'^testcases$', views.cases, name='testcases'),
    url(r'^testcases/(\d+)', views.case_detail, name='testcase_detail'),
    url(r'^results/(\d+)$', views.result_detail, name='result_detail'),
    url(r'^results/(\d+)/reset$', views.result_reset, name='result_reset'),
    url(r'^results/(\d+)/analysis$', views.result_analysis, name='result_analysis'),
    url(r'^results$', views.results, name='results'),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
