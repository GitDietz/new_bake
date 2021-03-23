from django.urls import reverse
from django.db import models
from django.db.models.functions import Lower
from django.conf import settings


# ## Model Managers ## #
class CategoryManager(models.Manager):
    def all(self):
        qs = super(CategoryManager, self).all()
        return qs

    def for_group_active(self, group_id):
        qs = super(CategoryManager, self).filter(active=True).filter(in_group=group_id)
        return qs

    def for_group_all(self, group_id):
        qs = super(CategoryManager, self).filter(in_group=group_id)
        return qs


class ItemManager(models.Manager):
    def all(self):
        qs = super(ItemManager, self).all()
        return qs

    def filter_by_instance(self, instance):
        obj_id = instance.id
        qs = super(ItemManager, self).filter(object_id=obj_id)
        return qs

    def to_get(self):
        qs = super(ItemManager, self).filter(purchased=None).filter(cancelled=None).order_by(Lower('description'))
        return qs

    def to_get_by_group(self, group_id):
        qs = super(ItemManager, self).filter(purchased=None).filter(cancelled=None).filter(in_group=group_id).order_by(Lower('description'))
        return qs

    def purchased(self):
        qs = super(ItemManager, self).filter(to_purchase=False)
        return qs


class MerchantManager(models.Manager):
    def all(self):
        qs = super(MerchantManager, self).all()
        return qs


class ShopGroupManager(models.Manager):
    def all(self):
        qs = super(ShopGroupManager, self).all()
        return qs

    def filter_by_instance(self, instance):
        obj_id = instance.id
        qs = super(ShopGroupManager, self).filter(object_id=obj_id)
        return qs

    def managed_by(self, user):
        qs = super(ShopGroupManager, self).filter(manager=user)
        return qs

    def create_group(self, name, manager):
        new_group = self.create(name=name, manager=manager, disabled=True)
        return new_group

    def member_of(self, user):
        qs = super(ShopGroupManager, self).filter(members=user)
        return qs

    def leaders(self, user):
        qs = super(ShopGroupManager, self).filter(leaders=user)
        return qs


class ReferenceManager(models.Manager):
    def all(self):
        qs = super(ReferenceManager, self).all()
        return qs


# ## Models ## #
class ShopGroup(models.Model):
    name = models.CharField(max_length=100, unique=True)
    purpose = models.CharField(max_length=200, blank=False)
    date_added = models.DateTimeField(auto_now=False, auto_now_add=True)
    manager = models.ForeignKey(settings.AUTH_USER_MODEL, default=1, related_name='manage_by', on_delete=models.CASCADE)
    members = models.ManyToManyField(settings.AUTH_USER_MODEL, blank=True, related_name='member_of')
    leaders = models.ManyToManyField(settings.AUTH_USER_MODEL, blank=True, related_name='leader_of')
    disabled = models.BooleanField(default=False)
    objects = ShopGroupManager()

    class Meta:
        ordering = ['name']

    def __str__(self):
        return self.name.title()

    def activate(self):
        self.disabled = False

    @property
    def info(self):
        label = f'Created by {self.manager} - {self.purpose}'
        return label


class Merchant(models.Model):
    name = models.CharField(max_length=50, unique=False, blank=False)
    date_added = models.DateField(auto_now=False, auto_now_add=True)
    for_group = models.ForeignKey(ShopGroup, blank=False, null=False, on_delete=models.CASCADE)
    objects = MerchantManager()

    class Meta:
        ordering = ['name']
        unique_together = ('name', 'for_group')

    def __str__(self):
        return self.name.title()


class Item(models.Model):
    requested = models.ForeignKey(settings.AUTH_USER_MODEL, default=1, related_name='req_by', on_delete=models.CASCADE)
    purchased = models.ForeignKey(settings.AUTH_USER_MODEL, blank=True, null=True, related_name='buy_by', on_delete=models.CASCADE)
    cancelled = models.ForeignKey(settings.AUTH_USER_MODEL, blank=True, null=True, related_name='cancel_by', on_delete=models.CASCADE)
    description = models.CharField(max_length=100)
    quantity = models.CharField(max_length=30, blank=True, null=True, default='1')
    date_requested = models.DateField(auto_now=False, auto_now_add=True)
    date_purchased = models.DateField(auto_now=False, auto_now_add=False, blank=True, null=True)
    to_get_from = models.ForeignKey(Merchant, blank=True, null=True, on_delete=models.CASCADE)
    in_group = models.ForeignKey(ShopGroup, blank=False, null=False, on_delete=models.CASCADE)
    # updated 1/1/20 blank=True, null=True,
    objects = ItemManager()

    class Meta:
        ordering = ['description']

    def __str__(self):
        this_merchant = self.to_get_from.name
        label = self.description.title()
        if len(self.quantity) > 0:
            label = label + '[' + self.quantity + ']'
        if this_merchant:
            label = label + ' @ ' + this_merchant
        return str(label)

    def get_absolute_url(self):
        return reverse("detail", kwargs={"id": self.id})

    @property
    def to_purchase(self):
        if self.date_purchased is None and self.cancelled is None:
            return True
        else:
            return False

    @property
    def name_qty(self):
        if len(self.quantity) > 0:
            return f'{self.description} [{self.quantity}]'
        else:
            return self.description


class Support(models.Model):
    log_by = models.ForeignKey(settings.AUTH_USER_MODEL, default=1, related_name='raise_by', on_delete=models.CASCADE)
    date_raised = models.DateField(auto_now=False, auto_now_add=True)
    issue = models.CharField(max_length=300)
    in_progress = models.BooleanField(default=False)
    resolved = models.BooleanField(default=False)
    resolution = models.CharField(max_length=300)
    date_closed = models.DateField(auto_now=False, auto_now_add=False, blank=True, null=True)

    def __str__(self):
        return str(self.issue)


class Category(models.Model):
    name = models.CharField(max_length=100)
    in_group = models.ForeignKey(ShopGroup, blank=False, null=False, on_delete=models.CASCADE)
    active = models.BooleanField(blank=False, null=False, default=True)
    objects = CategoryManager()

    class Meta:
        ordering = ['name']

    def __str__(self):
        label = self.name.title()
        return str(label)


class ReferenceItem(models.Model):
    created = models.ForeignKey(settings.AUTH_USER_MODEL, blank=True, null=True, related_name='created_by', on_delete=models.CASCADE)
    description = models.CharField(max_length=100)
    category = models.ForeignKey(Category, blank=True, null=True, on_delete=models.PROTECT)
    recommendation = models.CharField(max_length=100)
    date_added = models.DateField(auto_now=False, auto_now_add=True)
    in_group = models.ForeignKey(ShopGroup, blank=False, null=False, on_delete=models.CASCADE)
    objects = ReferenceManager()

    class Meta:
        ordering = ['description']

    def __str__(self):
        label = self.category + ':' + self.description.title()
        return str(label)





