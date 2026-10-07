# This file is part of the third-party Indico plugins.
# Copyright (C) 2026 CERN
#
# The third-party Indico plugins are free software; you can
# redistribute them and/or modify them under the terms of the;
# MIT License see the LICENSE file for more details.

from collections import defaultdict
from collections.abc import Collection, Sequence
from dataclasses import dataclass
from enum import Enum, auto
from typing import Literal

from marshmallow import ValidationError

from indico.core.db import db
from indico.modules.events.models.events import Event
from indico.modules.users.models.emails import UserEmail
from indico.modules.users.models.users import User

from indico_affiliation_extras.focal_points import get_event_catalog_affiliation_ids, get_event_catalog_focal_points
from indico_affiliation_extras.models.contacts import AffiliationContactList


type _RecipientIdentity = tuple[Literal['user'], int] | tuple[Literal['email'], str]


class AffiliationCatalogRecipientSource(Enum):
    focal_points = auto()
    contacts = auto()
    both = auto()


@dataclass(frozen=True)
class InvitationRecipient:
    first_name: str
    last_name: str
    email: str
    affiliation: str
    id: int | None = None
    is_primary: bool = False

    @property
    def identity_key(self) -> _RecipientIdentity:
        return ('user', self.id) if self.id is not None else ('email', self.email.lower())


def _get_catalog_contact_lists(
    affiliation_ids: set[int], contact_lists: Collection[str], include_unnamed_lists: bool,
) -> list[AffiliationContactList]:
    filters = []
    if contact_lists:
        filters.append(AffiliationContactList.name.in_(contact_lists))
    if include_unnamed_lists:
        filters.append(AffiliationContactList.name == '')  # noqa: PLC1901
    lists = []
    if filters and affiliation_ids:
        lists = (
            AffiliationContactList.query
            .filter(AffiliationContactList.affiliation_id.in_(affiliation_ids), db.or_(*filters))
            .order_by(AffiliationContactList.affiliation_id, AffiliationContactList.id)
            .all()
        )
    if set(contact_lists) - {contact_list.name for contact_list in lists}:
        raise ValidationError({'contact_lists': ['Unknown contact list']})
    if not any(contact_list.emails for contact_list in lists):
        raise ValidationError({'contact_lists': ['No contacts match the selected contact lists.']})
    return lists


def _get_focal_point_recipients(event: Event, affiliation_ids: set[int]) -> list[InvitationRecipient]:
    recipients = []
    for user in get_event_catalog_focal_points(event, affiliation_ids):
        if not user.email:
            continue
        affiliations = {
            entry.affiliation.name for entry in user.focal_point_entries
            if entry.affiliation_id in affiliation_ids
        }
        fallback_affiliation = next(iter(affiliations)) if len(affiliations) == 1 else ''
        recipients.append(InvitationRecipient(
            first_name=user.first_name,
            last_name=user.last_name,
            email=user.email,
            affiliation=user.affiliation or fallback_affiliation,
            id=user.id,
            is_primary=True,
        ))
    return recipients


def _get_contact_recipients(contact_lists: Sequence[AffiliationContactList]) -> list[InvitationRecipient]:
    affiliations_by_email: defaultdict[str, set[str]] = defaultdict(set)
    for contact_list in contact_lists:
        for email in contact_list.emails:
            affiliations_by_email[email].add(contact_list.affiliation.name)
    if not affiliations_by_email:
        return []

    users_by_email = {
        user_email.email: user_email.user
        for user_email in UserEmail.query.join(User, User.id == UserEmail.user_id).filter(
            UserEmail.email.in_(affiliations_by_email),
            ~UserEmail.is_user_deleted,
            ~User.is_deleted,
        )
    }
    recipients = []
    for email, affiliations in affiliations_by_email.items():
        user = users_by_email.get(email)
        fallback_affiliation = next(iter(affiliations)) if len(affiliations) == 1 else ''
        recipients.append(InvitationRecipient(
            first_name=user.first_name if user else '',
            last_name=user.last_name if user else '',
            email=email,
            affiliation=(user.affiliation if user else '') or fallback_affiliation,
            id=user.id if user else None,
            is_primary=user is not None and email == user.email.lower(),
        ))
    return recipients


def _combine_invitation_recipients(
    focal_points: Sequence[InvitationRecipient], contacts: Sequence[InvitationRecipient],
) -> list[InvitationRecipient]:
    unique_recipients: dict[_RecipientIdentity, InvitationRecipient] = {}
    for recipient in sorted(focal_points, key=lambda recipient: recipient.email.lower()):
        unique_recipients.setdefault(recipient.identity_key, recipient)
    for recipient in sorted(contacts, key=lambda recipient: (not recipient.is_primary, recipient.email.lower())):
        unique_recipients.setdefault(recipient.identity_key, recipient)
    return list(unique_recipients.values())


def get_affiliation_catalog_invitation_recipients(
    event: Event,
    *,
    recipient_source: AffiliationCatalogRecipientSource,
    contact_lists: Collection[str],
    include_unnamed_lists: bool,
) -> list[InvitationRecipient]:
    """Resolve catalog recipients, preferring focal points, listed primary emails, then alphabetical emails."""
    affiliation_ids = get_event_catalog_affiliation_ids(event)
    focal_points = []
    contacts = []
    if recipient_source in {AffiliationCatalogRecipientSource.focal_points, AffiliationCatalogRecipientSource.both}:
        focal_points = _get_focal_point_recipients(event, affiliation_ids)
    if recipient_source in {AffiliationCatalogRecipientSource.contacts, AffiliationCatalogRecipientSource.both}:
        lists = _get_catalog_contact_lists(affiliation_ids, contact_lists, include_unnamed_lists)
        contacts = _get_contact_recipients(lists)
    return _combine_invitation_recipients(focal_points, contacts)
