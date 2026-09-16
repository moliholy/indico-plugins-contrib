# This file is part of the third-party Indico plugins.
# Copyright (C) 2026 CERN
#
# The third-party Indico plugins are free software; you can
# redistribute them and/or modify them under the terms of the;
# MIT License see the LICENSE file for more details.

import pytest

from indico.modules.events import EventLogRealm
from indico.modules.events.registration.models.invitations import RegistrationInvitation
from indico.modules.logs import LogKind
from indico.modules.users.models.affiliations import Affiliation

from indico_affiliation_extras.models.catalogs import AffiliationCatalog
from indico_affiliation_extras.models.contacts import AffiliationContactList
from indico_affiliation_extras.models.focal_points import set_focal_points
from indico_affiliation_extras.models.lists import AffiliationList
from indico_affiliation_extras.settings import event_settings


pytest_plugins = 'indico.modules.events.registration.testing.fixtures'


def _login(test_client, user):
    with test_client.session_transaction() as sess:
        sess.set_session_user(user)


def _url(regform):
    return (
        f'/admin/plugins/affiliation_extras/events/{regform.event.id}/regforms/{regform.id}/affiliation-catalog/invite'
    )


def _affiliation_invite_url(regform):
    return f'/admin/plugins/affiliation_extras/events/{regform.event.id}/regforms/{regform.id}/invite'


def _metadata_url(regform):
    return f'{_url(regform)}/metadata'


def _recipient_count_url(regform):
    return f'{_url(regform)}/recipient-count'


def _add_event_catalog(db, event, affiliations):
    catalog = AffiliationCatalog(name='Catalog', event=event)
    db.session.add(catalog)
    db.session.flush()
    affiliation_list = AffiliationList(catalog=catalog, name='Representatives', position=1, is_enabled=True)
    affiliation_list.affiliations.update(affiliations)
    db.session.add(affiliation_list)
    db.session.flush()
    event_settings.set(event, 'default_catalog_id', catalog.id)


@pytest.mark.usefixtures('no_csrf_check')
def test_invite_affiliation_catalog_focal_points(
    test_client,
    db,
    dummy_regform,
    dummy_user,
    create_user,
    monkeypatch,
):
    monkeypatch.setattr('indico.modules.events.registration.util.notify_invitation', lambda *args, **kwargs: None)
    dummy_regform.event.update_principal(dummy_user, full_access=True)
    _login(test_client, dummy_user)

    managed = Affiliation(name='CERN')
    other = Affiliation(name='MIT')
    db.session.add_all([managed, other])
    db.session.flush()
    _add_event_catalog(db, dummy_regform.event, {managed})

    focal = create_user(1, first_name='Alice', last_name='Focal', email='alice@example.test')
    outside = create_user(2, first_name='Bob', last_name='Other', email='bob@example.test')
    set_focal_points(managed, {focal})
    set_focal_points(other, {outside})
    db.session.add(AffiliationContactList(affiliation=managed, name='Operations', emails=['contact@example.test']))
    db.session.flush()

    resp = test_client.post(
        _url(dummy_regform),
        json={
            'sender_address': dummy_user.email,
            'subject': 'Invitation',
            'body': 'Please register',
            'bcc_addresses': [],
            'copy_for_sender': False,
            'skip_moderation': False,
            'skip_access_check': False,
            'lock_email': False,
            'recipient_source': 'focal_points',
            'contact_lists': ['Operations'],
            'include_unnamed_lists': False,
        },
    )

    assert resp.status_code == 200
    assert resp.json['sent'] == 1
    assert resp.json['skipped'] == 0
    assert [inv.email for inv in dummy_regform.invitations] == ['alice@example.test']
    log_entry = dummy_regform.event.log_entries.filter_by(module='Registration').one()
    assert log_entry.data['Recipient source'] == 'focal_points'
    assert log_entry.data['Contact lists'] == []
    assert log_entry.data['Include unnamed contact lists'] is False


@pytest.mark.usefixtures('no_csrf_check')
def test_invite_affiliation_catalog_contacts(
    test_client,
    db,
    dummy_regform,
    dummy_user,
    monkeypatch,
):
    monkeypatch.setattr('indico.modules.events.registration.util.notify_invitation', lambda *args, **kwargs: None)
    dummy_regform.event.update_principal(dummy_user, full_access=True)
    _login(test_client, dummy_user)

    managed = Affiliation(name='CERN')
    outside = Affiliation(name='MIT')
    db.session.add_all((managed, outside))
    db.session.flush()
    _add_event_catalog(db, dummy_regform.event, {managed})
    db.session.add_all((
        AffiliationContactList(affiliation=managed, name='Operations', emails=['ops@example.test']),
        AffiliationContactList(affiliation=managed, name='', emails=['contact@example.test']),
        AffiliationContactList(affiliation=outside, name='Operations', emails=['outside@example.test']),
    ))
    db.session.flush()

    resp = test_client.post(
        _url(dummy_regform),
        json={
            'sender_address': dummy_user.email,
            'subject': 'Invitation',
            'body': 'Please register',
            'recipient_source': 'contacts',
            'contact_lists': ['Operations'],
            'include_unnamed_lists': True,
        },
    )

    assert resp.status_code == 200
    assert resp.json['sent'] == 2
    assert resp.json['skipped'] == 0
    assert {(inv.email, inv.affiliation) for inv in dummy_regform.invitations} == {
        ('contact@example.test', 'CERN'),
        ('ops@example.test', 'CERN'),
    }
    log_entry = dummy_regform.event.log_entries.filter_by(module='Registration').one()
    assert log_entry.realm == EventLogRealm.management
    assert log_entry.kind == LogKind.other
    assert log_entry.module == 'Registration'
    assert log_entry.summary == 'Invitations sent'
    assert log_entry.user == dummy_user
    assert log_entry.data['Invitation mode'] == 'Affiliation catalog'
    assert log_entry.data['Recipient source'] == 'contacts'
    assert log_entry.data['Contact lists'] == ['Operations']
    assert log_entry.data['Include unnamed contact lists'] is True


@pytest.mark.usefixtures('no_csrf_check')
def test_invite_affiliation_catalog_uses_matching_user_data(
    test_client,
    db,
    dummy_regform,
    dummy_user,
    create_user,
    monkeypatch,
):
    monkeypatch.setattr('indico.modules.events.registration.util.notify_invitation', lambda *args, **kwargs: None)
    dummy_regform.event.update_principal(dummy_user, full_access=True)
    _login(test_client, dummy_user)

    managed = Affiliation(name='CERN')
    db.session.add(managed)
    db.session.flush()
    _add_event_catalog(db, dummy_regform.event, {managed})
    contact_user = create_user(1, first_name='Alice', last_name='Contact', email='contact@example.test')
    contact_user.affiliation = 'WIPO'
    db.session.add(AffiliationContactList(affiliation=managed, name='Operations', emails=['contact@example.test']))
    db.session.flush()

    resp = test_client.post(
        _url(dummy_regform),
        json={
            'sender_address': dummy_user.email,
            'subject': 'Invitation',
            'body': 'Please register',
            'recipient_source': 'contacts',
            'contact_lists': ['Operations'],
            'include_unnamed_lists': False,
        },
    )

    assert resp.status_code == 200
    (invitation,) = dummy_regform.invitations
    assert (invitation.first_name, invitation.last_name, invitation.affiliation) == ('Alice', 'Contact', 'WIPO')


@pytest.mark.usefixtures('no_csrf_check')
def test_invite_affiliation_catalog_omits_ambiguous_affiliation(
    test_client,
    db,
    dummy_regform,
    dummy_user,
    monkeypatch,
):
    monkeypatch.setattr('indico.modules.events.registration.util.notify_invitation', lambda *args, **kwargs: None)
    dummy_regform.event.update_principal(dummy_user, full_access=True)
    _login(test_client, dummy_user)

    cern = Affiliation(name='CERN')
    wipo = Affiliation(name='WIPO')
    db.session.add_all((cern, wipo))
    db.session.flush()
    _add_event_catalog(db, dummy_regform.event, {cern, wipo})
    db.session.add_all((
        AffiliationContactList(affiliation=cern, name='Operations', emails=['shared@example.test']),
        AffiliationContactList(affiliation=wipo, name='Operations', emails=['shared@example.test']),
    ))
    db.session.flush()

    resp = test_client.post(
        _url(dummy_regform),
        json={
            'sender_address': dummy_user.email,
            'subject': 'Invitation',
            'body': 'Please register',
            'recipient_source': 'contacts',
            'contact_lists': ['Operations'],
            'include_unnamed_lists': False,
        },
    )

    assert resp.status_code == 200
    (invitation,) = dummy_regform.invitations
    assert invitation.affiliation == ''


@pytest.mark.usefixtures('no_csrf_check')
def test_invite_affiliation_catalog_returns_invitations_sorted_by_name(
    test_client,
    db,
    dummy_regform,
    dummy_user,
):
    dummy_regform.event.update_principal(dummy_user, full_access=True)
    _login(test_client, dummy_user)
    dummy_regform.invitations.extend((
        RegistrationInvitation(
            first_name='Alice',
            last_name='Zulu',
            email='alice.zulu@example.test',
            affiliation='CERN',
        ),
        RegistrationInvitation(
            first_name='Alice',
            last_name='Alpha',
            email='alice.alpha@example.test',
            affiliation='CERN',
        ),
    ))
    db.session.flush()

    resp = test_client.post(
        _url(dummy_regform),
        json={
            'sender_address': dummy_user.email,
            'subject': 'Invitation',
            'body': 'Please register',
            'bcc_addresses': [],
            'copy_for_sender': False,
            'skip_moderation': False,
            'skip_access_check': False,
            'lock_email': False,
            'recipient_source': 'focal_points',
            'contact_lists': [],
            'include_unnamed_lists': False,
        },
    )

    assert resp.status_code == 200
    assert [invitation['email'] for invitation in resp.json['invitation_list']] == [
        'alice.alpha@example.test',
        'alice.zulu@example.test',
    ]


@pytest.mark.usefixtures('no_csrf_check')
def test_invite_by_affiliation_invites_affiliation_users(
    test_client,
    db,
    dummy_regform,
    dummy_user,
    create_user,
    monkeypatch,
):
    monkeypatch.setattr('indico.modules.events.registration.util.notify_invitation', lambda *args, **kwargs: None)
    dummy_regform.event.update_principal(dummy_user, full_access=True)
    _login(test_client, dummy_user)

    managed = Affiliation(name='CERN')
    other = Affiliation(name='MIT')
    db.session.add_all([managed, other])
    db.session.flush()

    invited = create_user(1, first_name='Alice', last_name='Managed', email='alice@example.test')
    outside = create_user(2, first_name='Bob', last_name='Other', email='bob@example.test')
    invited.affiliation_link = managed
    outside.affiliation_link = other
    db.session.flush()

    resp = test_client.post(
        _affiliation_invite_url(dummy_regform),
        json={
            'sender_address': dummy_user.email,
            'subject': 'Invitation',
            'body': 'Please register',
            'bcc_addresses': [],
            'copy_for_sender': False,
            'skip_moderation': False,
            'skip_access_check': False,
            'lock_email': False,
            'affiliations': {'affiliations': [{'id': managed.id}], 'groups': [], 'tags': []},
        },
    )

    assert resp.status_code == 200
    assert resp.json['sent'] == 1
    assert resp.json['skipped'] == 0
    assert [inv.email for inv in dummy_regform.invitations] == ['alice@example.test']


def test_affiliation_catalog_invite_metadata(
    test_client,
    db,
    dummy_regform,
    dummy_user,
    create_user,
):
    dummy_regform.event.update_principal(dummy_user, full_access=True)
    _login(test_client, dummy_user)

    managed = Affiliation(name='CERN')
    unmanaged = Affiliation(name='MIT')
    db.session.add_all([managed, unmanaged])
    db.session.flush()
    _add_event_catalog(db, dummy_regform.event, {managed})

    set_focal_points(managed, {create_user(1)})
    set_focal_points(unmanaged, {create_user(2)})
    db.session.add_all((
        AffiliationContactList(affiliation=managed, name='Operations', emails=['ops@example.test']),
        AffiliationContactList(affiliation=managed, name='', emails=['contact@example.test']),
        AffiliationContactList(affiliation=unmanaged, name='Outside', emails=['outside@example.test']),
    ))
    db.session.flush()

    resp = test_client.get(_metadata_url(dummy_regform))

    assert resp.status_code == 200
    assert resp.json == {
        'affiliation_count': 1,
        'contact_list_options': ['Operations'],
        'focal_point_count': 1,
        'has_affiliation_catalog': True,
        'has_unnamed_contact_lists': True,
    }


def test_affiliation_catalog_invite_metadata_without_catalog(
    test_client,
    dummy_regform,
    dummy_user,
):
    dummy_regform.event.update_principal(dummy_user, full_access=True)
    _login(test_client, dummy_user)

    resp = test_client.get(_metadata_url(dummy_regform))

    assert resp.status_code == 200
    assert resp.json == {
        'affiliation_count': 0,
        'contact_list_options': [],
        'focal_point_count': 0,
        'has_affiliation_catalog': False,
        'has_unnamed_contact_lists': False,
    }


@pytest.mark.usefixtures('no_csrf_check')
def test_affiliation_catalog_invite_recipient_count_deduplicates_sources(
    test_client,
    db,
    dummy_regform,
    dummy_user,
    create_user,
):
    dummy_regform.event.update_principal(dummy_user, full_access=True)
    _login(test_client, dummy_user)

    managed = Affiliation(name='CERN')
    db.session.add(managed)
    db.session.flush()
    _add_event_catalog(db, dummy_regform.event, {managed})

    focal_point = create_user(1, email='shared@example.test')
    set_focal_points(managed, {focal_point})
    db.session.add(
        AffiliationContactList(
            affiliation=managed,
            name='Operations',
            emails=['shared@example.test', 'contact@example.test'],
        )
    )
    db.session.flush()

    resp = test_client.post(
        _recipient_count_url(dummy_regform),
        json={
            'recipient_source': 'both',
            'contact_lists': ['Operations'],
            'include_unnamed_lists': False,
        },
    )

    assert resp.status_code == 200
    assert resp.json == {'contact_recipient_count': 2, 'recipient_count': 2}


@pytest.mark.usefixtures('no_csrf_check')
def test_affiliation_catalog_invite_rejects_unknown_contact_list(
    test_client,
    db,
    dummy_regform,
    dummy_user,
):
    dummy_regform.event.update_principal(dummy_user, full_access=True)
    _login(test_client, dummy_user)

    managed = Affiliation(name='CERN')
    db.session.add(managed)
    db.session.flush()
    _add_event_catalog(db, dummy_regform.event, {managed})
    db.session.add(AffiliationContactList(affiliation=managed, name='Operations', emails=['ops@example.test']))
    db.session.flush()

    resp = test_client.post(
        _recipient_count_url(dummy_regform),
        json={
            'recipient_source': 'contacts',
            'contact_lists': ['Unknown'],
            'include_unnamed_lists': False,
        },
    )

    assert resp.status_code == 422
    assert 'contact_lists' in resp.json['webargs_errors']


@pytest.mark.usefixtures('no_csrf_check')
def test_affiliation_catalog_invite_recipient_count_requires_source(
    test_client,
    dummy_regform,
    dummy_user,
):
    dummy_regform.event.update_principal(dummy_user, full_access=True)
    _login(test_client, dummy_user)

    resp = test_client.post(
        _recipient_count_url(dummy_regform),
        json={
            'contact_lists': [],
            'include_unnamed_lists': False,
        },
    )

    assert resp.status_code == 422
    assert 'recipient_source' in resp.json['webargs_errors']


@pytest.mark.usefixtures('no_csrf_check')
def test_affiliation_catalog_invite_recipient_count_ignores_disabled_contacts(
    test_client,
    db,
    dummy_regform,
    dummy_user,
):
    dummy_regform.event.update_principal(dummy_user, full_access=True)
    _login(test_client, dummy_user)

    managed = Affiliation(name='CERN')
    db.session.add(managed)
    db.session.flush()
    _add_event_catalog(db, dummy_regform.event, {managed})
    db.session.add(AffiliationContactList(affiliation=managed, name='Operations', emails=['ops@example.test']))
    db.session.flush()

    resp = test_client.post(
        _recipient_count_url(dummy_regform),
        json={
            'recipient_source': 'focal_points',
            'contact_lists': ['Unknown'],
            'include_unnamed_lists': True,
        },
    )

    assert resp.status_code == 200
    assert resp.json == {'contact_recipient_count': 0, 'recipient_count': 0}


@pytest.mark.usefixtures('no_csrf_check')
@pytest.mark.parametrize('recipient_source', ('contacts', 'both'))
def test_invite_affiliation_catalog_rejects_no_contact_source(
    test_client,
    dummy_regform,
    dummy_user,
    recipient_source,
):
    dummy_regform.event.update_principal(dummy_user, full_access=True)
    _login(test_client, dummy_user)

    resp = test_client.post(
        _url(dummy_regform),
        json={
            'sender_address': dummy_user.email,
            'subject': 'Invitation',
            'body': 'Please register',
            'recipient_source': recipient_source,
            'contact_lists': [],
            'include_unnamed_lists': False,
        },
    )

    assert resp.status_code == 422
    assert '_schema' in resp.json['webargs_errors']
