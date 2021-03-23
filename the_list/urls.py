from django.urls import path, re_path

from .views import *

app_name = 'the_list'

urlpatterns = [
     path('list/', shop_list, name='shop_list'),
     path('create/', shop_create, name='shop_create'),
    path('groups/create', group_detail, name='group_create'),
    re_path('groups/delete/(?P<pk>\d+)', group_delete, name='group_delete'),
    re_path('groups/maintain/(?P<pk>\d+)', group_maintenance, name='group_maintenance'),
    re_path('groups/make_leader/(?P<pk>\d+)(?P<sep>#)(?P<user_id>\d+)', group_make_leader, name='group_make_leader'),
    re_path('groups/add_member/(?P<pk>\d+)(?P<sep>#)(?P<user_id>\d+)', group_add_member, name='group_add_member'),
    re_path('groups/remove_self/(?P<pk>\d+)', group_remove_self, name='group_remove_self'),
    re_path('groups/remove_leader/(?P<pk>\d+)(?P<sep>#)(?P<user_id>\d+)', group_remove_leader, name='group_remove_leader'),
    re_path('groups/remove_member/(?P<pk>\d+)(?P<sep>#)(?P<user_id>\d+)', group_remove_member, name='group_remove_member'),
    path('groups/', group_list, name='group_list'),
    path('group_select/', user_group_select, name='group_select'),
    path('merchants/', merchant_list, name='merchant_list'),
    path('merchants/create', merchant_create, name='merchant_create'),
    re_path('merchants/(?P<pk>\d+)', merchant_update, name='merchant_update'),
    re_path('merchants/delete/(?P<pk>\d+)', merchant_delete, name='merchant_delete'),
    re_path('(?P<pk>\d+)/', shop_detail, name='shop_edit'),
    path('support/', support, name='support'),
]

