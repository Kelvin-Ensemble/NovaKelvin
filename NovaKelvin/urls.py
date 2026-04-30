"""
URL configuration for NovaKelvin project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/5.2/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.contrib import admin
from django.urls import include, path, re_path
from django.conf import settings

from main_site import views as ms_views
from ticketing import views as ts_views

import django_saml2_auth.views


urlpatterns = [
    # SAML2 URLs — must come BEFORE other url patterns
    re_path(r'^sso/', include('django_saml2_auth.urls')),

    # Replace default login with SAML login
    re_path(r'^accounts/login/$', django_saml2_auth.views.signin),

    # Optionally replace admin login too
    re_path(r'^admin/login/$', django_saml2_auth.views.signin),
    path('admin/', admin.site.urls),
    path('', ms_views.home, name='home'),
    path('about', ms_views.about, name='about'),
    path('about/committee', ms_views.committee, name='committee'),
    path('about/past-concerts', ms_views.pastconcerts, name='pastconcerts'),
    path('about/join', ms_views.joinus, name='joinus'),

    path("tickets/", ts_views.ticketing_page, name="ticketing_home"),
    path("tickets/success", ts_views.ticketing_success, name="ticketing_success"),

    path('api/', include('api.urls')),  # Add this line

]

if settings.DEBUG:
    # Include django_browser_reload URLs only in DEBUG mode
    urlpatterns += [
        path("__reload__/", include("django_browser_reload.urls")),
    ]
