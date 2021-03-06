from django.conf.urls.defaults import patterns, url
from api.views import check_in, loginview, leave, accept, decline, complete, fail, get, loc_update, c2dmkey_update

urlpatterns = patterns('',
    url(r'^login/', loginview, name="api_login"),
    url(r'^check_in/', check_in, name="api_checkin"),
    url(r'^leave/', leave, name="api_leave"),

    url(r'^loc_update/', loc_update, name="api_loc_update"),
    url(r'^c2dmkey_update/', c2dmkey_update, name="c2dmkey_update"),

    url(r'^get/', get, name="api_get"),
    url(r'^accept/', accept, name="api_accept"),
    url(r'^decline/', decline, name="api_decline"),
    
    url(r'^complete/', complete, name="api_complete"),
    url(r'^fail/', fail, name="api_fail"),
)
