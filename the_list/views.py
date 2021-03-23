from datetime import date
import logging

from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.contrib.sites.models import Site
from django.core.exceptions import ValidationError
from django.urls import reverse
from django.db import DatabaseError
from django.db.models import Q
from django.shortcuts import render, get_object_or_404, HttpResponseRedirect, Http404, redirect

from .forms import CategoryForm, ItemForm, MerchantForm, ShopGroupForm, UsersGroupsForm, NewGroupCreateForm, SupportLogForm
from .models import Item, Merchant, ShopGroup, Support
from .utils import get_object_id, in_post


def get_session_list_choice(request):
    """
    get the list choice from session or set it using the first group this user is in
    handle the odd case when user is not in a group - should not happen outside DEV
    """
    try:
        logging.getLogger("info_logger").info("get session choice")
        list_active = request.session['list'] # the session can contain value that is no longer in DB
        if list_active != '':
            logging.getLogger("info_logger").info(f"session value = {list_active}")
            if ShopGroup.objects.filter(id=list_active).exists():
                return list_active
            else:
                logging.getLogger("info_logger").info('No such value in DB, new selection required')
                request.session.pop('list')
                return None
        else:
            logging.getLogger("info_logger").info(f"session NO value = {list_active}")
            return None
    except KeyError:
        logging.getLogger("info_logger").info(f'no list in session, getting first option from DB')
        list_choices = ShopGroup.objects.filter(members=request.user)
        if list_choices:
            select_item = list_choices.first().id
            request.session['list'] = select_item
            return select_item
        else:
            return None


def get_user_list_property(request):
    """
    get the list information for the user
    :return: multiple values
    """
    logging.getLogger("info_logger").info(f"get multiple properties | user = {request.user.username}")
    list_choices = ShopGroup.objects.filter(members=request.user)
    list_active_no = get_session_list_choice(request)
    active_list_name = ShopGroup.objects.filter(id=list_active_no).first()
    user_list_options = list_choices.count()
    logging.getLogger("info_logger").info(f'active list is {active_list_name}')
    return list_choices, user_list_options, list_active_no, active_list_name


def is_user_leader(request, list_no):
    """"to return boolean indicating that the particular user is a leader and can close/delete items"""
    logging.getLogger("info_logger").info(f"user = {request.user.username}")
    leader_in_group = ShopGroup.objects.filter(id=list_no).filter(leaders=request.user).first()
    if leader_in_group:
        logging.getLogger("info_logger").info(f' user is leader')
        return True
    else:
        logging.getLogger("info_logger").info(f' user is not leader')
        return False


#  #################################  ITEM / AKA Shop #################################
@login_required
def shop_create(request):
    """
    responds to the item create template
    if 'add multiple items' is selected on the submit button the same submission form will return
    else the list view will be returned
    """
    logging.getLogger("info_logger").info(f"view entered | user = {request.user.username}")
    list_choices, user_list_options, list_active_no, active_list_name = get_user_list_property(request)
    form = ItemForm(request.POST or None, list=list_active_no)
    title = 'Add purchase items'
    notice = ''
    if form.is_valid():
        logging.getLogger("info_logger").info(f"form valid | user = {request.user.username}")

        # get the objects still to purchase and check if this new one is among them
        qs_tobuy = Item.objects.to_get()
        item = form.save(commit=False)
        for_group = ShopGroup.objects.filter(id=list_active_no).first()
        this_found = qs_tobuy.filter(Q(description__iexact=item.description) & Q(in_group=for_group))

        if this_found:
            logging.getLogger("info_logger").info(f"item exists | user = {request.user.username}")
            notice = 'Already listed : ' + item.description
        else:
            logging.getLogger("info_logger").info(f"item will be added | user = {request.user.username}")
            item.in_group = for_group
            item.description = item.description.title()
            item.requested = request.user
            vendor_id = item.to_get_from
            logging.getLogger("info_logger").info(f"item saving for vendor = {vendor_id}")
            item.to_get_from = vendor_id  # this_merchant
            item.date_requested = date.today()
            item.save()
            notice = 'Added ' + item.description

        if 'add_one' in request.POST:
            return redirect('shop:shop_list')
        else:
            form = ItemForm(None, list=list_active_no)

    context = {
        'title': title,
        'form': form,
        'notice': notice,
        'selected_list': active_list_name,
        'no_of_lists': user_list_options,
    }
    return render(request, 'item_create.html', context)


@login_required
def shop_list(request):
    """
    shows the list of unfulfilled items in the particular list
    responds to item cancel requests and item fulfilled requests
    also hands off to the item edit view
    list will only be one the user is a member of
    """
    domain = Site.objects.get_current()
    # print(f' domain is {domain}')
    logging.getLogger("info_logger").info(f"view entry | user = {request.user.username}")
    list_choices = ShopGroup.objects.filter(members=request.user)
    if not list_choices:
        logging.getLogger("info_logger").info(f"user has no groups redirect to create?")
        return redirect('shop:group_list')
    list_active_no = get_session_list_choice(request)
    if list_active_no is None:
        logging.getLogger("info_logger").info(f"redirect to group selection | user = {request.user.username}")
        redirect('shop:group_select')
    active_list_name = ShopGroup.objects.filter(id=list_active_no).first()
    leader_names = list(active_list_name.leaders.all().values_list('username', flat=True))
    # method above to create list: .values('fieldname') will create a tuple with key and value
    lead = ', '.join(leader_names)

    user_list_options = list_choices.count()

    logging.getLogger("info_logger").info(f"active list is {active_list_name} | user = {request.user.username}")
    # leader status allows user to see the action buttons and to perform their actions
    leader_status = is_user_leader(request, list_active_no)

    if request.user.is_authenticated:
        queryset_list = Item.objects.to_get_by_group(list_active_no)
        notice = ''
        if request.POST:
            logging.getLogger("info_logger").info(f"form submitted | user = {request.user.username}")
            logging.getLogger("info_logger").info(f"which item to purchase or cancel | user = {request.user.username}")
            cancel_item = in_post(request.POST, 'cancel_item')
            purchased_item = in_post(request.POST, 'got_item')

            if cancel_item != 0 or purchased_item != 0:
                item_to_update = max(cancel_item, purchased_item)
                instance = get_object_or_404(Item, id=item_to_update)
                if instance.requested == request.user or leader_status:
                    if cancel_item != 0:
                        logging.getLogger("info_logger").info(f'to cancel item {cancel_item}')
                        instance.cancelled = request.user
                    elif purchased_item != 0:
                        logging.getLogger("info_logger").info(f'purchased item {purchased_item}')
                        instance.purchased = request.user
                        instance.date_purchased = date.today()
                    instance.save()
            else:
                logging.getLogger("info_logger").info(f'No objects to update')
        elif request.POST:
            notice = "You can't update the items"
            logging.getLogger("info_logger").info(f"no permission to update | user = {request.user.username}")

        context = {
            'title': 'Your list',
            'object_list': queryset_list,
            'active_list': active_list_name,
            'user_lists': user_list_options,
            'is_leader': leader_status,
            'notice': notice,
            'leader_list': lead,
        }
        return render(request, 'item_list.html', context)
    else:
        raise Http404


@login_required
def shop_detail(request, pk):
    """
    allows the edit of the item if its the requestor or the leader/s of the group
    :param pk: for the instance of the item
    :param request:
    :return: divert to shoplist
    """
    logging.getLogger("info_logger").info(f"user = {request.user.username}")
    item = get_object_or_404(Item, pk=pk)
    active_list = item.in_group.id
    user_is_leader = False
    if request.user in item.in_group.leaders.all():
        user_is_leader = True

    if request.user == item.requested or user_is_leader:
        if request.method == "POST":
            logging.getLogger("info_logger").info(f"Posted form | user = {request.user.username}")
            form = ItemForm(request.POST, instance=item, list=active_list)
            if form.is_valid():
                logging.getLogger("info_logger").info(f"valid form submitted | user = {request.user.username}")
                form.save()
                return HttpResponseRedirect(reverse('shop:shop_list'))

        template_name = 'item_detail.html'
        context = {
            'title': 'Update Item',
            'form': ItemForm(instance=item, list=active_list),
            'notice': '',
        }
        return render(request, template_name, context)
    else:
        logging.getLogger("info_logger").info(f"diverting to the list view | user = {request.user.username}")
        return redirect('shop:shop_list')


#  ################################# reference list views #################################
@login_required
def category_create(request):

    list_choices, user_list_options, list_active_no, active_list_name = get_user_list_property(request)
    form = CategoryForm(request.POST or None, list=list_active_no, default=active_list_name)
    if request.method == "POST":
        logging.getLogger("info_logger").info(f'from submitted')
        if form.is_valid():
            try:
                item = form.save(commit=False)
                item.name = form.cleaned_data['name'].title()
                # Adding list reference
                # item.for_group = active_list_name
                item.save()
                return HttpResponseRedirect(reverse('shop:merchant_list'))
            except DatabaseError:
                raise ValidationError('That Merchant already exists in this group')
        else:
            logging.getLogger("info_logger").info(f'Error on form {form.errors}')

    template_name = 'merchant.html'
    context = {
        'title': 'Create Merchant',
        'form': form,
        'notice': '',
    }
    return render(request, template_name, context)


@login_required
def reference_create(request):
    """
    create reference list item
    """
    logging.getLogger("info_logger").info(f"reference create | user = {request.user.username}")
    # list_choices, user_list_options, list_active_no, active_list_name = get_user_list_property(request)
    form = ItemForm(request.POST or None, list=list_active_no)
    title = 'Add purchase items'
    notice = ''
    if form.is_valid():
        logging.getLogger("info_logger").info(f"form valid | user = {request.user.username}")

        # get the objects still to purchase and check if this new one is among them
        qs_tobuy = Item.objects.to_get()
        item = form.save(commit=False)
        for_group = ShopGroup.objects.filter(id=list_active_no).first()
        this_found = qs_tobuy.filter(Q(description__iexact=item.description) & Q(in_group=for_group))

        if this_found:
            logging.getLogger("info_logger").info(f"item exists | user = {request.user.username}")
            notice = 'Already listed : ' + item.description
        else:
            logging.getLogger("info_logger").info(f"item will be added | user = {request.user.username}")
            item.in_group = for_group
            item.description = item.description.title()
            item.requested = request.user
            vendor_id = item.to_get_from
            logging.getLogger("info_logger").info(f"item saving for vendor = {vendor_id}")
            item.to_get_from = vendor_id  # this_merchant
            item.date_requested = date.today()
            item.save()
            notice = 'Added ' + item.description

        if 'add_one' in request.POST:
            return redirect('shop:shop_list')
        else:
            form = ItemForm(None, list=list_active_no)

    context = {
        'title': title,
        'form': form,
        'notice': notice,
        'selected_list': active_list_name,
        'no_of_lists': user_list_options,
    }
    return render(request, 'item_create.html', context)


#  ################################# Support #################################
@login_required
def support(request):
    logging.getLogger("info_logger").info(f'user = {request.user.username}')
    template = 'support.html'
    form = SupportLogForm(request.POST or None)
    force_repeats = False
    form_option = 'lodge'
    message = ''
    user_requests = Support.objects.filter(log_by=request.user)
    if user_requests.count() > 10:
        form_option = 'repeat'
        message = 'You  have a number of outstanding requests already, please wait for these to be resolved'
    else:
        if request.method == 'POST':
            if form.is_valid():
                case = form.save(commit=False)
                case.log_by = request.user
                case.save()
                context = {
                    'form_option': 'done',
                    'message_content': "Your request is recorded, we'll attend to it as soon as possible",
                }
        else:
            context = {
                'form': form,
                'form_option': form_option,
                'message_content': message,
            }
    return render(request, template, context)


#  ################################# User's GROUP #################################
@login_required
def user_group_select(request):
    logging.getLogger("info_logger").info(f'user = {request.user.username}')
    notice = ''
    logging.getLogger("info_logger").info(f'get the lists the user is member of')
    list_choices = ShopGroup.objects.filter(members=request.user)
    # pass the members groups to form
    group_form = UsersGroupsForm(data=ShopGroup.objects.filter(members=request.user))
    logging.getLogger("info_logger").info(f'list of groups {list_choices}')
    template_name = 'group_select.html'

    if request.method == 'POST':
        select_item = in_post(request.POST, 'pick_item')
        if select_item != 0:
            request.session['list'] = select_item
            logging.getLogger("info_logger").info(f'selected list is {select_item}')
            return redirect('shop:shop_list')
        else:
            notice = 'No list selected'
            logging.getLogger("info_logger").info(f'nothing selected, return to form')

    context = {
        'title': 'Please select which group you want to view and edit',
        'form': group_form,
        'list_choices': list_choices,
        'notice': notice,
    }
    return render(request, template_name, context)


#  ################################# GROUP #################################
@login_required
def group_detail(request, pk=None, shopgroup_obj=None):
    logging.getLogger("info_logger").info(f'user = {request.user.username}| id = {pk}')
    if pk:
        shopgroup_obj = get_object_or_404(ShopGroup, pk=pk)

    if request.method == "POST":
        form = NewGroupCreateForm(request.POST, instance=shopgroup_obj)
        if form.is_valid():
            new_group = form.save(commit=False)
            new_group.name = form.cleaned_data['joining']
            new_group.purpose = form.cleaned_data['purpose']
            new_group.manager = request.user
            new_group.save()
            new_group.members.add(request.user)
            new_group.leaders.add(request.user)

            return HttpResponseRedirect(reverse('shop:group_list'))
        else:
            logging.getLogger("info_logger").info(f'Form errors: {form.errors}')
    else:
        form = NewGroupCreateForm(instance=shopgroup_obj) # will be none if new

    template_name = 'group.html'
    logging.getLogger("info_logger").info(f'Outside Post section')
    context = {
        'title': 'Create or Update Group',
        'form': form,
        'notice': '',
    }
    return render(request, template_name, context)


@login_required
def group_maintenance(request, pk=None):
    logging.getLogger("info_logger").info(f'user = {request.user.username}| id = {pk}')
    if pk:
        this_group = ShopGroup.objects.get(id=pk)
        # the assumption here is that the member/leader/manager structure is correct
        all_members = this_group.members.all()
        leaders = this_group.leaders.all()
        members = all_members.exclude(pk__in=leaders)
        all_users = User.objects.all()
        unrelated = all_users.exclude(pk__in=all_members)
        if settings.DEBUG:
            mode = 'DEBUG'
        else:
            mode = 'PROD'
        notice = ''
        if request.method == "POST":
            pass
        context = {
            'title': f'Group maintenance',
            'group_name': this_group.name,
            'leader_list': leaders,
            'member_list': members,
            'unrelated': unrelated,
            'group_id': pk,
            'notice': notice,
            'mode': mode,
        }
        return render(request, 'group_manage.html', context)
    else:
        return redirect('shop:group_list')


@login_required
def group_list(request):
    logging.getLogger("info_logger").info(f'user = {request.user.username}')
    managed_list = ShopGroup.objects.managed_by(request.user)
    member_list = ShopGroup.objects.member_of(request.user)
    notice = ''
    context = {
        'title': 'Group List',
        'managed_list': managed_list,
        'member_list': member_list,
        'notice': notice,
    }
    return render(request, 'group_list.html', context)
    # else:
    #     return redirect('shop:shop_list')


@login_required()
def group_delete(request, pk):
    group = get_object_or_404(ShopGroup, pk=pk)
    managed_group = ShopGroup.objects.managed_by(request.user)
    if group in managed_group:
        if request.method == 'POST':
            group.delete()
            return HttpResponseRedirect(reverse('shop:group_list'))

        template_name = 'group_delete.html'
        context = {
            'title': 'Delete group',
            'object': group,
            'notice': '',
        }
        return render(request, template_name, context)
    else:
        context = {
            'title': 'Delete group',
            'object': group,
            'no_delete': 'You are not the manager of the group and can''t delete it',}

        return render(request, "group_action_reject.html", context)

@login_required()
def group_remove_self(request, pk):
    """
    when the user removes himself from the group. A different view for Managers to remove other members
    """
    group = get_object_or_404(ShopGroup, pk=pk)
    group.members.remove(request.user)
    # if this is the last member, delete the group
    if group.members.count() == 0:
        group.delete()
    return redirect('shop:group_list')


@login_required()
def group_remove_leader(request, pk, sep, user_id):
    """
    when the manager wants to remove the Leader role from a user
    """
    logging.getLogger("info_logger").info(f'group = {pk}, user to remove as leader = {user_id}')
    group = get_object_or_404(ShopGroup, pk=pk)
    group.leaders.remove(user_id)
    return redirect('shop:group_maintenance', pk=pk)


@login_required()
def group_remove_member(request, pk, sep, user_id):
    logging.getLogger("info_logger").info(f'group = {pk}, user to remove as member = {user_id}')
    group = get_object_or_404(ShopGroup, pk=pk)
    group.members.remove(user_id)
    return redirect('shop:group_maintenance', pk=pk)


@login_required()
def group_make_leader(request, pk, sep, user_id):
    logging.getLogger("info_logger").info(f'group = {pk}, user to add as leader = {user_id}')
    group = get_object_or_404(ShopGroup, pk=pk)
    group.leaders.add(user_id)
    return redirect('shop:group_maintenance', pk=pk)


@login_required()
def group_add_member(request, pk, sep, user_id):
    logging.getLogger("info_logger").info(f'group = {pk}, user to add as leader = {user_id}')
    group = get_object_or_404(ShopGroup, pk=pk)
    group.members.add(user_id)
    return redirect('shop:group_maintenance', pk=pk)

# ################################# MERCHANT #################################

@login_required
def merchant_list(request):
    logging.getLogger("info_logger").info(f'user = {request.user.username}')
    list_choices, user_list_options, list_active_no, active_list_name = get_user_list_property(request)
    queryset_list = Merchant.objects.filter(for_group_id=list_active_no)
    notice = ''
    context = {
        'title': 'Merchant List',
        'object_list': queryset_list,
        'notice': notice,
    }
    return render(request, 'merchant_list.html', context)


@login_required
def merchant_detail(request, id=None):
    # 10/1/20 mod to use list as part of merchant model
    logging.getLogger("info_logger").info(f'user = {request.user.username}')
    instance = get_object_or_404(Merchant, id=id)
    form = MerchantForm(request.POST or None)
    list_choices, user_list_options, list_active_no, active_list_name = get_user_list_property(request)
    title = 'Add or Edit Merchant'
    notice = ''
    if request.method == 'POST' and form.is_valid():
        logging.getLogger("info_logger").info(f'valid form')

        qs = Merchant.objects.all()
        form.save(commit=False)
        this_found = qs.filter(Q(name__iexact=Merchant.name))
        if this_found:
            logging.getLogger("info_logger").info(f'Merchant already in list')
            notice = 'Already listed ' + Merchant.name.title()
        else:
            logging.getLogger("info_logger").info(f'ok will add {Merchant.name} to list')
            Merchant.name = Merchant.title()
            # Adding list reference
            Merchant.for_group = active_list_name
            Merchant.save()
            notice = 'Added ' + Merchant.name

        return redirect('shop:merchant_list')

    context = {
        'title': title,
        'form': form,
        'notice': notice,
        'instance': instance
    }
    return render(request, 'merchant.html', context)


@login_required
def merchant_create(request):
    # 10/1/20 now need to have the group instance available to add

    list_choices, user_list_options, list_active_no, active_list_name = get_user_list_property(request)
    form = MerchantForm(request.POST or None, list=list_active_no, default=active_list_name)
    if request.method == "POST":
        logging.getLogger("info_logger").info(f'from submitted')
        if form.is_valid():
            try:
                item = form.save(commit=False)
                item.name = form.cleaned_data['name'].title()
                # Adding list reference
                # item.for_group = active_list_name
                item.save()
                return HttpResponseRedirect(reverse('shop:merchant_list'))
            except DatabaseError:
                raise ValidationError('That Merchant already exists in this group')
        else:
            logging.getLogger("info_logger").info(f'Error on form {form.errors}')

    template_name = 'merchant.html'
    context = {
        'title': 'Create Merchant',
        'form': form,
        'notice': '',
    }
    return render(request, template_name, context)


@login_required
def merchant_update(request, pk):
    merchant = get_object_or_404(Merchant, pk=pk)
    list = merchant.for_group
    if request.method == "POST":
        logging.getLogger("info_logger").info(f'form submitted')
        form = MerchantForm(request.POST, instance=merchant, list=list.id, default=list)
        if form.is_valid():
            form.save()
            logging.getLogger("info_logger").info(f'complete - direct to list')
            return HttpResponseRedirect(reverse('shop:merchant_list'))

    template_name = 'merchant.html'
    context = {
        'title': 'Update Merchant',
        'form': MerchantForm(instance=merchant, list=list.id, default=list),
        'notice': '',
    }
    return render(request, template_name, context)


@login_required
def merchant_delete(request, pk):
    merchant = get_object_or_404(Merchant, pk=pk)
    # users = User.objects.all()
    # if the user is a leader then allow to remove a group

    if request.method == 'POST':
        this_group = merchant.for_group
        leader = is_user_leader(request, this_group.id)
        if leader:
            merchant.delete()
            logging.getLogger("info_logger").info(f'merchant deleted')
        return HttpResponseRedirect(reverse('shop:merchant_list'))

    template_name = 'merchant_delete.html'
    context = {
        'title': 'Delete Merchant',
        'object': merchant,
        'notice': '',
    }
    return render(request, template_name, context)

# ################################# Experimental USER #################################
# 30/3/20 none used

@login_required
def search(request):
    user_list = User.objects.all()
    user_filter = UserFilter(request.GET, queryset=user_list)
    return render(request, 'user_list.html', {'filter': user_filter})


@login_required
def simple_item_list(request):
    item_list = Item.objects.to_get()
    group_filter = GroupFilter(request.GET, queryset=item_list)
    return render(request, 'filter_list.html', {'filter': group_filter})
