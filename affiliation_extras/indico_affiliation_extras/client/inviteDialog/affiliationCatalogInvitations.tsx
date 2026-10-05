// This file is part of the third-party Indico plugins.
// Copyright (C) 2026 CERN
//
// The third-party Indico plugins are free software; you can
// redistribute them and/or modify them under the terms of the;
// MIT License see the LICENSE file for more details.

import affiliationCatalogInviteMetadataURL from 'indico-url:plugin_affiliation_extras.api_affiliation_catalog_invite_metadata';
import affiliationCatalogInviteRecipientCountURL from 'indico-url:plugin_affiliation_extras.api_affiliation_catalog_invite_recipient_count';
import inviteAffiliationCatalogURL from 'indico-url:plugin_affiliation_extras.api_invite_affiliation_catalog';

import React, {useEffect, useMemo} from 'react';
import {useForm, useFormState} from 'react-final-form';
import {Icon, Loader, Message, Segment} from 'semantic-ui-react';

import {FinalCheckbox} from 'indico/react/forms';
import {useIndicoAxios} from 'indico/react/hooks';
import {Param, Plural, PluralTranslate, Singular, Translate} from 'indico/react/i18n';

import ContactListRecipientFields from '../components/ContactListRecipientFields';

interface AffiliationCatalogFieldsProps {
  eventId: number;
  regformId: number;
}

interface AffiliationCatalogInvitationValues {
  affiliation_catalog_recipient_count: number;
  include_focal_points: boolean;
  include_contacts: boolean;
  contact_lists: string[];
  include_unnamed_lists: boolean;
}

interface AffiliationCatalogMetadata {
  affiliationCount: number;
  focalPointCount: number;
  contactListOptions: string[];
  hasUnnamedContactLists: boolean;
}

interface RecipientCountData {
  recipientCount: number;
}

interface InvitationModeContext {
  eventId: number;
  regformId: number;
}

interface AffiliationCatalogInvitationMode {
  key: string;
  buttonLabel: string;
  Component: React.ComponentType<AffiliationCatalogFieldsProps>;
  extraFields: (keyof AffiliationCatalogInvitationValues)[];
  initialValues: AffiliationCatalogInvitationValues;
  getCount: (values: AffiliationCatalogInvitationValues) => number;
  getSubmitURL: (context: InvitationModeContext) => string;
}

const AffiliationCatalogFields = ({eventId, regformId}: AffiliationCatalogFieldsProps) => {
  const form = useForm<AffiliationCatalogInvitationValues>();
  const {
    values: {
      include_focal_points: includeFocalPoints = false,
      include_contacts: includeContacts = false,
      contact_lists: contactLists = [],
      include_unnamed_lists: includeUnnamedLists = false,
    },
  } = useFormState<AffiliationCatalogInvitationValues>({subscription: {values: true}});
  const {data: metadataData, loading} = useIndicoAxios(
    affiliationCatalogInviteMetadataURL({event_id: eventId, reg_form_id: regformId}),
    {camelize: true}
  );
  const data = metadataData as AffiliationCatalogMetadata | null;
  const recipientCountConfig = useMemo(
    () => ({
      url: affiliationCatalogInviteRecipientCountURL({
        event_id: eventId,
        reg_form_id: regformId,
      }),
      method: 'POST',
      data: {
        include_focal_points: includeFocalPoints,
        include_contacts: includeContacts,
        contact_lists: contactLists,
        include_unnamed_lists: includeUnnamedLists,
      },
    }),
    [contactLists, eventId, includeContacts, includeFocalPoints, includeUnnamedLists, regformId]
  );
  const {
    data: recipientCountResponse,
    error: recipientCountError,
    loading: recipientCountLoading,
  } = useIndicoAxios(recipientCountConfig, {camelize: true});
  const recipientCountData = recipientCountResponse as RecipientCountData | null;
  const hasUnnamedContactLists = data && data.hasUnnamedContactLists;
  const hasContactLists = !!(
    data &&
    (data.contactListOptions.length || data.hasUnnamedContactLists)
  );

  useEffect(() => {
    form.change('affiliation_catalog_recipient_count', 0);
  }, [form, recipientCountConfig]);

  useEffect(() => {
    if (!recipientCountLoading && !recipientCountError && recipientCountData) {
      form.change('affiliation_catalog_recipient_count', recipientCountData.recipientCount);
    }
  }, [form, recipientCountData, recipientCountError, recipientCountLoading]);

  useEffect(() => {
    if (hasUnnamedContactLists === false && includeUnnamedLists) {
      form.change('include_unnamed_lists', false);
    }
  }, [form, hasUnnamedContactLists, includeUnnamedLists]);

  useEffect(() => {
    if (data && !hasContactLists && includeContacts) {
      form.change('include_contacts', false);
    }
  }, [data, form, hasContactLists, includeContacts]);

  if (loading || !data) {
    return <Loader active inline="centered" />;
  }

  return (
    <>
      {data.affiliationCount ? (
        <Message info icon>
          <Icon name="building outline" />
          <Message.Content>
            <PluralTranslate as={Message.Header} count={data.affiliationCount}>
              <Singular>
                The event catalog contains <Param name="count" value={data.affiliationCount} />{' '}
                affiliation.
              </Singular>
              <Plural>
                The event catalog contains <Param name="count" value={data.affiliationCount} />{' '}
                affiliations.
              </Plural>
            </PluralTranslate>
            <Translate as="p">
              Select the affiliation contacts that should receive an invitation.
            </Translate>
            <Translate as="p">Existing invitations and registrations will be skipped.</Translate>
          </Message.Content>
        </Message>
      ) : (
        <Message error icon>
          <Icon name="warning sign" />
          <Message.Content>
            <Translate as={Message.Header}>No affiliations found</Translate>
            <Translate as="p">No affiliations were found in this event catalog.</Translate>
          </Message.Content>
        </Message>
      )}
      <FinalCheckbox
        name="include_focal_points"
        label={Translate.string('Invite focal points')}
        value={undefined}
        description={
          data.focalPointCount
            ? PluralTranslate.string(
                '{count} focal point from the catalog will be invited.',
                '{count} focal points from the catalog will be invited.',
                data.focalPointCount,
                {count: data.focalPointCount}
              )
            : Translate.string('No focal points were found in the event catalog.')
        }
        disabled={!data.focalPointCount}
        showAsToggle
      />
      <FinalCheckbox
        name="include_contacts"
        label={Translate.string('Invite contacts')}
        value={undefined}
        description={
          hasContactLists
            ? Translate.string('Invite contacts from selected contact lists.')
            : Translate.string('No contact lists were found in the event catalog.')
        }
        disabled={!hasContactLists}
        showAsToggle
      />
      {data.contactListOptions.length > 0 && (
        <Segment>
          <ContactListRecipientFields
            contactListOptions={data.affiliationCount ? data.contactListOptions : []}
            hasUnnamedContactLists={data.hasUnnamedContactLists}
            disabled={!includeContacts}
            allowNoContactLists
          />
        </Segment>
      )}
    </>
  );
};

const affiliationCatalogInvitations: AffiliationCatalogInvitationMode = {
  key: 'affiliation_catalog',
  buttonLabel: Translate.string('Affiliation Catalog'),
  Component: AffiliationCatalogFields,
  extraFields: [
    'include_focal_points',
    'include_contacts',
    'contact_lists',
    'include_unnamed_lists',
  ],
  initialValues: {
    affiliation_catalog_recipient_count: 0,
    include_focal_points: true,
    include_contacts: true,
    contact_lists: [],
    include_unnamed_lists: true,
  },
  getCount: ({affiliation_catalog_recipient_count: recipientCount}) => recipientCount,
  getSubmitURL: ({eventId, regformId}) =>
    inviteAffiliationCatalogURL({event_id: eventId, reg_form_id: regformId}),
};

export default affiliationCatalogInvitations;
