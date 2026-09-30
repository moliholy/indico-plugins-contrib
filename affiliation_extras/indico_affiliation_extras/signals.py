# This file is part of the third-party Indico plugins.
# Copyright (C) 2026 CERN
#
# The third-party Indico plugins are free software; you can
# redistribute them and/or modify them under the terms of the;
# MIT License see the LICENSE file for more details.

from blinker import Namespace


_signals = Namespace()


affiliation_list_saved = _signals.signal(
    'affiliation-list-saved',
    """
Called after a catalog list has been created or updated. The *sender* is the
`AffiliationList`. `plugin_data` is the dict submitted for the list, which
other plugins can use to store their own per-list settings. When the list
was created by cloning a catalog, `source` is the list it was cloned from,
otherwise it is `None`.
""",
)
