#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
.. $Id$
"""

from __future__ import print_function, absolute_import, division
__docformat__ = "restructuredtext en"

logger = __import__('logging').getLogger(__name__)

from zope import lifecycleevent

from pyramid import httpexceptions as hexc

from pyramid.view import view_config
from pyramid.view import view_defaults

from nti.app.base.abstract_views import AbstractAuthenticatedView

from nti.app.contenttypes.presentation import MessageFactory as _

from nti.app.contenttypes.presentation.interfaces import ILessonPublicationConstraintValidator

from nti.app.contenttypes.presentation.views import VIEW_NODE_MOVE

from nti.app.products.courseware.views.view_mixins import AbstractChildMoveView

from nti.app.externalization.error import raise_json_error

from nti.appserver.dataserver_pyramid_views import GenericGetView

from nti.appserver.ugd_edit_views import UGDPutView
from nti.appserver.ugd_edit_views import UGDPostView
from nti.appserver.ugd_edit_views import UGDDeleteView

from nti.contenttypes.presentation.interfaces import INTILessonOverview
from nti.contenttypes.presentation.interfaces import INTICourseOverviewGroup
from nti.contenttypes.presentation.interfaces import ILessonPublicationConstraint
from nti.contenttypes.presentation.interfaces import ILessonPublicationConstraints

from nti.contenttypes.presentation.interfaces import OverviewGroupMovedEvent
from nti.contenttypes.presentation.interfaces import PresentationAssetMovedEvent

from nti.dataserver import authorization as nauth

from nti.externalization.externalization import to_external_object

from nti.externalization.interfaces import StandardExternalFields

TOTAL = StandardExternalFields.TOTAL
ITEM_COUNT = StandardExternalFields.ITEM_COUNT


@view_config(route_name='objects.generic.traversal',
             request_method='POST',
             context=INTILessonOverview,
             permission=nauth.ACT_CONTENT_EDIT,
             renderer='rest',
             name=VIEW_NODE_MOVE)
class LessonOverviewMoveView(AbstractChildMoveView):
    """
    Move the given object between lessons or overview groups. For
    overview groups, we need to resolve the given ntiid as an
    asset ref in the old parent (or new parent if moving internally).

    :raises HTTPUnprocessableEntity if we do not find the given ntiid
            underneath the old parent
    """

    notify_type = None

    def _get_context_ntiid(self):
        return self.context.ntiid

    def _remove_from_parent(self, parent, obj):
        return parent.remove(obj)

    def _get_children_ntiids(self, parent_ntiid):
        result = set()
        result.add(parent_ntiid)

        def _recur(node):
            val = getattr(node, 'ntiid', None)
            if val:
                result.add(val)
            try:
                for child in node.Items or ():
                    _recur(child)
            except AttributeError:
                pass
        _recur(self.context)
        return result

    def _get_ref_in_parent(self, ntiid, parent):
        # XXX: If the client were to pass us OIDs (to the refs),
        # this code could disappear.
        # Assuming one hit per parent...We actually ensure
        # that in the group itself (only for videos).
        for child in list(parent):
            # We want to move the actual ref, but clients will
            # only send target ntiids.
            if     ntiid == getattr(child, 'target', '') \
                or ntiid == getattr(child, 'ntiid', ''):
                return child
        return None

    def _set_notify_type(self, obj):
        if INTICourseOverviewGroup.providedBy(obj):
            self.notify_type = OverviewGroupMovedEvent
        else:
            self.notify_type = PresentationAssetMovedEvent

    def _get_object_to_move(self, ntiid, old_parent=None):
        if old_parent is not None:
            # Need a to convert any non-ref into the ref.
            obj = self._get_ref_in_parent(ntiid, old_parent)
            if obj is None:
                raise_json_error(self.request,
                                 hexc.HTTPUnprocessableEntity,
                                 {
                                     'message': _(u'No ref found for given media ntiid.'),
                                     'code': 'NoRefFound',
                                     'field': 'ntiid'
                                 },
                                 None)
        self._set_notify_type(obj)
        return obj


@view_config(context=ILessonPublicationConstraints)
@view_defaults(route_name='objects.generic.traversal',
               renderer='rest',
               request_method='GET',
               permission=nauth.ACT_CONTENT_EDIT)
class LessonPublicationConstraintsGetView(GenericGetView):

    def _do_call(self, constraints):
        result = to_external_object(constraints)
        result[TOTAL] = result[ITEM_COUNT] = len(constraints)
        result.__parent__ = self.context
        result.__name__ = self.request.view_name
        result.lastModified = constraints.lastModified
        return result

    def __call__(self):
        return self._do_call(self.context)


@view_config(context=ILessonPublicationConstraints)
@view_defaults(route_name='objects.generic.traversal',
               name='clear',
               renderer='rest',
               request_method='POST',
               permission=nauth.ACT_CONTENT_EDIT)
class LessonPublicationConstraintsClearView(AbstractAuthenticatedView):

    def __call__(self):
        self.context.clear()
        return self.context


@view_config(context=ILessonPublicationConstraints)
@view_defaults(route_name='objects.generic.traversal',
               renderer='rest',
               request_method='POST',
               permission=nauth.ACT_CONTENT_EDIT)
class LessonPublicationConstraintsPostView(UGDPostView):

    content_predicate = ILessonPublicationConstraint.providedBy

    def _do_call(self):
        creator = self.remoteUser
        constraint = self.readCreateUpdateContentObject(creator,
                                                        search_owner=False)
        constraint.creator = creator.username
        constraint.updateLastMod()

        try:
            validator = ILessonPublicationConstraintValidator(constraint)
            validator.validate()
        except Exception as e:
            raise_json_error(self.request,
                             hexc.HTTPUnprocessableEntity,
                             {
                                 'message': str(e),
                                 'code': 'ConstraintValidationError',
                             },
                             None)

        lifecycleevent.created(constraint)
        self.context.append(constraint)
        self.request.response.status_int = 201
        return constraint


@view_config(context=ILessonPublicationConstraint)
@view_defaults(route_name='objects.generic.traversal',
               renderer='rest',
               request_method='PUT',
               permission=nauth.ACT_CONTENT_EDIT)
class LessonCompletionConstraintPutView(UGDPutView):

    def updateContentObject(self, contentObject, externalValue, set_id=False,
                            notify=True, pre_hook=None, object_hook=None):
        result = UGDPutView.updateContentObject(self, contentObject, externalValue,
                                                set_id=set_id, notify=notify,
                                                pre_hook=pre_hook,
                                                object_hook=object_hook)
        try:
            validator = ILessonPublicationConstraintValidator(contentObject)
            validator.validate()
        except Exception as e:
            raise_json_error(self.request,
                             hexc.HTTPUnprocessableEntity,
                             {
                                 'message': str(e),
                                 'code': 'ConstraintValidationError',
                             },
                             None)
        return result


@view_config(route_name="objects.generic.traversal",
             context=ILessonPublicationConstraint,
             renderer='rest',
             permission=nauth.ACT_DELETE,
             request_method='DELETE')
class LessonPublicationConstraintDeleteView(UGDDeleteView):

    def _do_delete_object(self, theObject):
        del theObject.__parent__[theObject.__name__]
        return theObject
