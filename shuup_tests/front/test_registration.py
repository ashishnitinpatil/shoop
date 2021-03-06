# -*- coding: utf-8 -*-
# This file is part of Shuup.
#
# Copyright (c) 2012-2017, Shoop Commerce Ltd. All rights reserved.
#
# This source code is licensed under the OSL-3.0 license found in the
# LICENSE file in the root directory of this source tree.
import re
import uuid

import pytest
from django.conf import settings
from django.contrib.auth import get_user_model
from django.core import mail
from django.core.urlresolvers import reverse
from django.test.utils import override_settings

from shuup import configuration
from shuup.core.models import CompanyContact
from shuup.core.models import PersonContact
from shuup.notify.models import Script
from shuup.testing.factories import get_default_shop

username = "u-%d" % uuid.uuid4().time
email = "%s@shuup.local" % username


@pytest.mark.django_db
@pytest.mark.parametrize("requiring_activation", (False, True))
def test_registration(django_user_model, client, requiring_activation):
    if "shuup.front.apps.registration" not in settings.INSTALLED_APPS:
        pytest.skip("shuup.front.apps.registration required in installed apps")

    get_default_shop()

    with override_settings(
        SHUUP_REGISTRATION_REQUIRES_ACTIVATION=requiring_activation,
    ):
        client.post(reverse("shuup:registration_register"), data={
            "username": username,
            "email": email,
            "password1": "password",
            "password2": "password",
        })
        user = django_user_model.objects.get(username=username)
        if requiring_activation:
            assert not user.is_active
        else:
            assert user.is_active

@pytest.mark.django_db
@pytest.mark.parametrize("requiring_activation", (False, True))
def test_registration_2(django_user_model, client, requiring_activation):
    if "shuup.front.apps.registration" not in settings.INSTALLED_APPS:
        pytest.skip("shuup.front.apps.registration required in installed apps")

    get_default_shop()

    with override_settings(
        SHUUP_REGISTRATION_REQUIRES_ACTIVATION=requiring_activation,
    ):
        response = client.post(reverse("shuup:registration_register"), data={
            "username": username,
            "email": email,
            "password1": "password",
            "password2": "password",
            "next": reverse('shuup:checkout')
        })
        user = django_user_model.objects.get(username=username)
        assert response.status_code == 302 #redirect
        assert response.url.endswith(reverse('shuup:checkout'))


def test_settings_has_account_activation_days():
    assert hasattr(settings, 'ACCOUNT_ACTIVATION_DAYS')


@pytest.mark.django_db
def test_password_recovery_user_receives_email_1(client):
    get_default_shop()
    user = get_user_model().objects.create_user(
        username="random_person",
        password="asdfg",
        email="random@shuup.local"
    )
    n_outbox_pre = len(mail.outbox)
    client.post(
        reverse("shuup:recover_password"),
        data={
            "email": user.email
        }
    )
    assert (len(mail.outbox) == n_outbox_pre + 1), "Sending recovery email has failed"
    assert 'http' in mail.outbox[-1].body, "No recovery url in email"
    # ticket #SHUUP-606
    assert 'site_name' not in mail.outbox[-1].body, "site_name variable has no content"


@pytest.mark.django_db
def test_password_recovery_user_receives_email_2(client):
    get_default_shop()
    user = get_user_model().objects.create_user(
        username="random_person",
        password="asdfg",
        email="random@shuup.local"
    )
    n_outbox_pre = len(mail.outbox)
    # Recover with username
    client.post(
        reverse("shuup:recover_password"),
        data={
            "username": user.username
        }
    )
    assert (len(mail.outbox) == n_outbox_pre + 1), "Sending recovery email has failed"
    assert 'http' in mail.outbox[-1].body, "No recovery url in email"
    assert 'site_name' not in mail.outbox[-1].body, "site_name variable has no content"


@pytest.mark.django_db
def test_password_recovery_user_receives_email_3(client):
    get_default_shop()
    user = get_user_model().objects.create_user(
        username="random_person",
        password="asdfg",
        email="random@shuup.local"
    )
    get_user_model().objects.create_user(
        username="another_random_person",
        password="asdfg",
        email="random@shuup.local"
    )

    n_outbox_pre = len(mail.outbox)
    # Recover all users with email random@shuup.local
    client.post(
        reverse("shuup:recover_password"),
        data={
            "email": user.email
        }
    )
    assert (len(mail.outbox) == n_outbox_pre + 2), "Sending 2 recovery emails has failed"
    assert 'http' in mail.outbox[-1].body, "No recovery url in email"
    assert 'site_name' not in mail.outbox[-1].body, "site_name variable has no content"


@pytest.mark.django_db
def test_password_recovery_user_with_no_email(client):
    get_default_shop()
    user = get_user_model().objects.create_user(
        username="random_person",
        password="asdfg"
    )
    n_outbox_pre = len(mail.outbox)
    client.post(
        reverse("shuup:recover_password"),
        data={
            "username": user.username
        }
    )
    assert (len(mail.outbox) == n_outbox_pre), "No recovery emails sent"


@pytest.mark.django_db
def test_user_will_be_redirected_to_user_account_page_after_activation(client):
    """
    1. Register user
    2. Dig out the urls from the email
    3. Get the url and see where it redirects
    4. See that user's email is in content (in input)
    5. Check that the url poins to user_account-page
    """
    if "shuup.front.apps.registration" not in settings.INSTALLED_APPS:
        pytest.skip("shuup.front.apps.registration required in installed apps")
    if "shuup.front.apps.customer_information" not in settings.INSTALLED_APPS:
        pytest.skip("shuup.front.apps.customer_information required in installed apps")

    get_default_shop()
    response = client.post(reverse("shuup:registration_register"), data={
        "username": username,
        "email": email,
        "password1": "password",
        "password2": "password",
    }, follow=True)
    body = mail.outbox[-1].body
    urls = re.findall('http[s]?://(?:[a-zA-Z]|[0-9]|[$-_@.&+]|[!*\(\),]|(?:%[0-9a-fA-F][0-9a-fA-F]))+', body)
    response = client.get(urls[0], follow=True)
    assert email.encode('utf-8') in response.content, 'email should be found from the page.'
    assert reverse('shuup:customer_edit') == response.request['PATH_INFO'], 'user should be on the account-page.'


@pytest.mark.django_db
@pytest.mark.parametrize("allow_company_registration", (False, True))
def test_company_registration(django_user_model, client, allow_company_registration):
    if "shuup.front.apps.registration" not in settings.INSTALLED_APPS:
        pytest.skip("shuup.front.apps.registration required in installed apps")

    get_default_shop()

    configuration.set(None, "allow_company_registration", allow_company_registration)

    url = reverse("shuup:registration_register_company")
    Script.objects.create(
        event_identifier="company_approved_by_admin",
        name="Send Company Activated Email",
        enabled=True,
        template="company_activated_email",
        _step_data=[
            {'actions': [
                {
                    'fallback_language': {'constant': 'en'},
                    'template_data': {
                        'pt-br': {'content_type': 'html', 'subject': '', 'body': ''},
                        'en': {
                            'content_type': 'html',
                            'subject': 'Company activated',
                            'body': '{{customer.pk}} - activated'
                        },
                        'base': {'content_type': 'html', 'subject': '', 'body': ''},
                        'it': {'content_type': 'html', 'subject': '', 'body': ''},
                        'ja': {'content_type': 'html', 'subject': '', 'body': ''},
                        'zh-hans': {'content_type': 'html', 'subject': '', 'body': ''},
                        'fi': {'content_type': 'html', 'subject': '', 'body': ''}
                    },
                    'recipient': {'variable': 'customer_email'},
                    'language': {'variable': 'language'},
                    'identifier': 'send_email'}
            ],
                'enabled': True,
                'next': 'stop',
                'conditions': [],
                'cond_op': 'all'
            }
        ]
    )
    Script.objects.create(
        event_identifier="company_registration_received",
        name="Send Company Registration Received Email",
        enabled=True,
        template="company_registration_received_email",
        _step_data=[
            {
                'conditions': [],
                'next': 'stop',
                'cond_op': 'all',
                'actions': [
                    {
                        'fallback_language': {'constant': 'en'},
                        'template_data': {
                            'pt-br': {'content_type': 'html', 'subject': '', 'body': ''},
                             'en': {'content_type': 'html', 'subject': 'Generic welcome message', 'body': 'Welcome!'},
                             'base': {'content_type': 'html', 'subject': '', 'body': ''},
                             'it': {'content_type': 'html', 'subject': '', 'body': ''},
                             'ja': {'content_type': 'html', 'subject': '', 'body': ''},
                             'zh-hans': {'content_type': 'html', 'subject': '', 'body': ''},
                             'fi': {'content_type': 'html', 'subject': '', 'body': ''}
                        },
                        'recipient': {'variable': 'customer_email'},
                        'language': {'variable': 'language'},
                        'identifier': 'send_email'
                    },
                    {
                        'fallback_language': {'constant': 'en'},
                        'template_data': {
                            'pt-br': {'content_type': 'plain', 'subject': 'New company registered', 'body': ''},
                            'en': {'content_type': 'plain', 'subject': 'New company registered', 'body': 'New company registered'},
                            'it': {'content_type': 'plain', 'subject': 'New company registered', 'body': ''},
                            'ja': {'content_type': 'plain', 'subject': 'New company registered', 'body': ''},
                            'zh-hans': {'content_type': 'plain', 'subject': 'New company registered', 'body': ''},
                            'fi': {'content_type': 'plain', 'subject': 'New company registered', 'body': ''}
                        },
                        'recipient': {'constant': 'admin@host.local'},
                        'language': {'constant': 'en'},
                        'identifier': 'send_email'
                    }
                ],
                'enabled': True}],
    )
    if not allow_company_registration:
        response = client.get(url)
        assert response.status_code == 404
    else:
        response = client.post(url, data={
            'company-name': "Test company",
            'company-name_ext': "test",
            'company-tax_number': "12345",
            'company-email': "test@example.com",
            'company-phone': "123123",
            'company-www': "",
            'billing-street': "testa tesat",
            'billing-street2': "",
            'billing-postal_code': "12345",
            'billing-city': "test test",
            'billing-region': "",
            'billing-region_code': "",
            'billing-country': "FI",
            'contact_person-first_name': "Test",
            'contact_person-last_name': "Tester",
            'contact_person-email': email,
            'contact_person-phone': "123",
            'user_account-username': username,
            'user_account-password1': "password",
            'user_account-password2': "password",
        })

        user = django_user_model.objects.get(username=username)
        contact = PersonContact.objects.get(user=user)
        company = CompanyContact.objects.get(members__in=[contact])

        # one of each got created
        assert django_user_model.objects.count() == 1
        assert PersonContact.objects.count() == 1
        assert CompanyContact.objects.count() == 1
        # and they are innactive
        assert PersonContact.objects.filter(is_active=False).count() == 1
        assert CompanyContact.objects.filter(is_active=False).count() == 1
        assert mail.outbox[0].subject == "Generic welcome message"
        assert mail.outbox[1].subject == "New company registered"
        company = CompanyContact.objects.first()
        company.is_active = True
        company.save(update_fields=("is_active",))
        assert mail.outbox[2].subject == "Company activated"
