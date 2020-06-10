from django.shortcuts import render, get_object_or_404, redirect
from django.conf import settings
from django.core.exceptions import ObjectDoesNotExist
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin
from django.views.generic import ListView, DetailView, View
from django.utils import timezone
from django.contrib import messages

from .models import Item, OrderItem, Order, BillingAddress, Payment
from .forms import CheckoutForm

import stripe
stripe.api_key = settings.STRIPE_SECRET_KEY


class IndexView(ListView):
    model = Item
    paginate_by = 10
    template_name = 'shop/index.html'
    context_object_name = 'items'


class CheckoutView(View):
    def get(self, *args, **kwargs):
        # form
        form = CheckoutForm()
        context = {
            'form': form
        }
        return render(self.request, 'shop/checkout.html', context)

    def post(self, *args, **kwargs):
        form = CheckoutForm(self.request.POST or None)
        try:
            order = Order.objects.get(user=self.request.user, ordered=False)
            if form.is_valid():
                street_address = form.cleaned_data.get('street_address')
                apartment_address = form.cleaned_data.get('apartment_address')
                country = form.cleaned_data.get('country')
                zip = form.cleaned_data.get('zip')
                # TODO: add functionality for these fields
                # same_shipping_address = form.cleaned_data.get(
                #     'same_shipping_address')
                # save_info = form.cleaned_data.get('save_info')
                payment_option = form.cleaned_data.get('payment_option')
                billing_address = BillingAddress(
                    user=self.request.user,
                    street_address=street_address,
                    apartment_address=apartment_address,
                    country=country,
                    zip=zip
                )
                billing_address.save()
                order.billing_address = billing_address
                order.save()

                if payment_option == 'S':
                    return redirect('shop:payment', payment_option='stripe')
                elif payment_option == 'P':
                    return redirect('shop:payment', payment_option='paypal')
                else:
                    messages.warning(self.request, 'Invalid payment option selected')
                    return redirect('shop:checkout')
        except ObjectDoesNotExist:
            messages.error(self.request, 'You don\'t have an active order')
            return redirect('shop:cart')


class PaymentView(View):
    def get(self, *args, **kwargs):
        order = Order.objects.get(user=self.request.user, ordered=False)
        context = {
            'order': order
        }
        return render(self.request, 'shop/payment.html', context)

    def post(self, *args, **kwargs):
        order = Order.objects.get(user=self.request.user, ordered=False)
        token = self.request.POST.get('stripeToken')
        amount = int(order.get_total() * 100)

        try:
            charge = stripe.Charge.create(
                amount=amount,
                currency='usd',
                source=token,
            )

            # create the payment
            payment = Payment()
            payment.stripe_charge_id = charge['id']
            payment.user = self.request.user
            payment.amount = order.get_total()
            payment.save()

            # assign the payment to the order
            order.ordered = True
            order.payment = payment
            order.save()

            messages.success(self.request, 'Your order was successful!')
            return redirect('/')

        except stripe.error.CardError as e:
            body = e.json_body
            err = body.get('error', {})
            messages.warning(self.request, f"{err.get('message')}")
            return redirect('/')
        except stripe.error.RateLimitError as e:
            messages.warning(self.request, 'Rate limit error')
            return redirect('/')
        except stripe.error.InvalidRequestError as e:
            messages.warning(self.request, 'InvalidRequestError')
            return redirect('/')
        except stripe.error.AuthenticationError as e:
            messages.warning(self.request, 'AuthenticationError')
            return redirect('/')
        except stripe.error.APIConnectionError as e:
            messages.warning(self.request, 'APIConnectionError')
            return redirect('/')
        except stripe.error.StripeError as e:
            messages.warning(self.request, 'StripeError')
            return redirect('/')
        except Exception as e:
            messages.warning(
                self.request, 'A serious error occured')
            return redirect('/')

            # send an email to ourselves
            pass


class ProductView(DetailView):
    model = Item
    template_name = 'shop/product.html'
    context_object_name = 'product'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        if self.request.user.is_active:
            context['order'] = Order.objects.get(
                user=self.request.user, ordered=False)
        return context


class CartView(LoginRequiredMixin, View):
    def get(self, *args, **kwargs):
        try:
            order = Order.objects.get(user=self.request.user, ordered=False)
            context = {
                'order': order
            }
            return render(self.request, 'shop/cart.html', context)
        except ObjectDoesNotExist:
            messages.error(self.request, 'You don\'t have an active order')
            return redirect('/')


@login_required
def add_to_cart(request, slug):
    item = get_object_or_404(Item, slug=slug)
    order_item, created = OrderItem.objects.get_or_create(
        item=item, user=request.user, ordered=False)
    order_qs = Order.objects.filter(user=request.user, ordered=False)
    if order_qs.exists():
        order = order_qs[0]
        # check if the order item is in the order
        if order.items.filter(item__slug=item.slug).exists():
            order_item.quantity += 1
            order_item.save()
            messages.info(
                request, f'This item quantity is {order_item.quantity}')
            return redirect('shop:product', slug=slug)
        else:
            order.items.add(order_item)
            messages.info(request, 'This item was added to your cart')
            return redirect('shop:product', slug=slug)
    else:
        ordered_date = timezone.now()
        order = Order.objects.create(
            user=request.user, ordered_date=ordered_date)
        order.items.add(order_item)
        messages.info(request, 'This item was added to your cart')
        return redirect('shop:product', slug=slug)


@login_required
def remove_from_cart(request, slug):
    item = get_object_or_404(Item, slug=slug)
    order_qs = Order.objects.filter(user=request.user, ordered=False)
    if order_qs.exists():
        order = order_qs[0]
        # check if the order item is in the order
        if order.items.filter(item__slug=item.slug).exists():
            order_item = OrderItem.objects.filter(
                item=item, user=request.user, ordered=False)[0]
            order_item.quantity = 1
            order_item.save()
            order.items.remove(order_item)
            messages.info(request, 'This item was removed from your cart')
            return redirect('shop:cart')
        else:
            messages.info(request, 'This item was not in your cart')
            return redirect('shop:product', slug=slug)
    else:
        messages.info(request, 'You don\'t have an active order')
        return redirect('shop:product', slug=slug)


@login_required
def remove_single_item_from_cart(request, slug):
    item = get_object_or_404(Item, slug=slug)
    order_qs = Order.objects.filter(user=request.user, ordered=False)
    if order_qs.exists():
        order = order_qs[0]
        # check if the order item is in the order
        if order.items.filter(item__slug=item.slug).exists():
            order_item = OrderItem.objects.filter(
                item=item, user=request.user, ordered=False)[0]
            if order_item.quantity > 1:
                order_item.quantity -= 1
                order_item.save()
            else:
                order.items.remove(order_item)
            messages.info(request, 'This item quantity was updated')
            return redirect('shop:cart')
        else:
            messages.info(request, 'This item was not in your cart')
            return redirect('shop:product', slug=slug)
    else:
        messages.info(request, 'You don\'t have an active order')
        return redirect('shop:product', slug=slug)


@login_required
def add_single_item_to_cart(request, slug):
    item = get_object_or_404(Item, slug=slug)
    order_item, created = OrderItem.objects.get_or_create(
        item=item, user=request.user, ordered=False)
    order_qs = Order.objects.filter(user=request.user, ordered=False)
    if order_qs.exists():
        order = order_qs[0]
        # check if the order item is in the order
        if order.items.filter(item__slug=item.slug).exists():
            order_item.quantity += 1
            order_item.save()
            messages.info(request, 'This item quantity was updated')
            return redirect('shop:cart')
        else:
            order.items.add(order_item)
            messages.info(request, 'This item was added to your cart')
            return redirect('shop:cart')
    else:
        ordered_date = timezone.now()
        order = Order.objects.create(
            user=request.user, ordered_date=ordered_date)
        order.items.add(order_item)
        messages.info(request, 'This item was added to your cart')
        return redirect('shop:cart')


@login_required
def remove_single_item_from_product(request, slug):
    item = get_object_or_404(Item, slug=slug)
    order_qs = Order.objects.filter(user=request.user, ordered=False)
    if order_qs.exists():
        order = order_qs[0]
        # check if the order item is in the order
        if order.items.filter(item__slug=item.slug).exists():
            order_item = OrderItem.objects.filter(
                item=item, user=request.user, ordered=False)[0]
            if order_item.quantity > 1:
                order_item.quantity -= 1
                order_item.save()
            else:
                order.items.remove(order_item)
            messages.info(request, 'This item quantity was updated')
            return redirect('shop:product', slug=slug)
        else:
            messages.info(request, 'This item was not in your cart')
            return redirect('shop:product', slug=slug)
    else:
        messages.info(request, 'You don\'t have an active order')
        return redirect('shop:product', slug=slug)


@login_required
def add_single_item_from_product(request, slug):
    item = get_object_or_404(Item, slug=slug)
    order_item, created = OrderItem.objects.get_or_create(
        item=item, user=request.user, ordered=False)
    order_qs = Order.objects.filter(user=request.user, ordered=False)
    if order_qs.exists():
        order = order_qs[0]
        # check if the order item is in the order
        if order.items.filter(item__slug=item.slug).exists():
            order_item.quantity += 1
            order_item.save()
            messages.info(request, 'This item quantity was updated')
            return redirect('shop:product', slug=slug)
        else:
            order.items.add(order_item)
            messages.info(request, 'This item was added to your cart')
            return redirect('shop:product', slug=slug)
    else:
        ordered_date = timezone.now()
        order = Order.objects.create(
            user=request.user, ordered_date=ordered_date)
        order.items.add(order_item)
        messages.info(request, 'This item was added to your cart')
        return redirect('shop:product', slug=slug)
