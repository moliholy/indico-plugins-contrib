// This file is part of the third-party Indico plugins.
// Copyright (C) 2026 CERN
//
// The third-party Indico plugins are free software; you can
// redistribute them and/or modify them under the terms of the;
// MIT License see the LICENSE file for more details.

import React from 'react';
import {Field, useForm} from 'react-final-form';

import {FinalCheckbox, FinalDropdown} from 'indico/react/forms';
import {Translate} from 'indico/react/i18n';

interface ContactListRecipientFormValues {
  contact_lists: string[];
  include_unnamed_lists: boolean;
}

export default function ContactListRecipientFields({
  contactListOptions,
  allowNoContactLists = false,
  hasUnnamedContactLists = true,
}: {
  contactListOptions: string[];
  allowNoContactLists?: boolean;
  hasUnnamedContactLists?: boolean;
}) {
  const form = useForm<ContactListRecipientFormValues>();
  return (
    <>
      <FinalDropdown
        name="contact_lists"
        label={Translate.string('Recipients')}
        placeholder={
          allowNoContactLists
            ? Translate.string('Select contact lists')
            : Translate.string('Send to all contact lists')
        }
        options={contactListOptions.map(name => ({value: name, text: name}))}
        disabled={!contactListOptions.length}
        onChange={(value: string[]) => {
          if (!allowNoContactLists && value.length === 0) {
            form.change('include_unnamed_lists', true);
          }
        }}
        selection
        multiple
        fluid
      />
      <Field<string[]> name="contact_lists" subscription={{value: true}}>
        {({input: {value: contactLists}}) => (
          <FinalCheckbox
            name="include_unnamed_lists"
            label={Translate.string('Send to contacts in unnamed lists')}
            value={undefined}
            disabled={
              !hasUnnamedContactLists ||
              !contactListOptions.length ||
              (!allowNoContactLists && !contactLists.length)
            }
            showAsToggle
          />
        )}
      </Field>
    </>
  );
}
