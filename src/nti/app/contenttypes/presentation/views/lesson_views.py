#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
.. $Id$
"""

from __future__ import print_function, unicode_literals, absolute_import, division
__docformat__ = "restructuredtext en"

logger = __import__('logging').getLogger(__name__)

from zope import interface
from zope import lifecycleevent

from pyramid import httpexceptions as hexc

from pyramid.view import view_config
from pyramid.view import view_defaults

from nti.app.contenttypes.presentation.interfaces import ILessonPublicationConstraintValidator

from nti.app.externalization.error import raise_json_error

from nti.appserver.dataserver_pyramid_views import GenericGetView

from nti.appserver.ugd_edit_views import UGDPutView
from nti.appserver.ugd_edit_views import UGDPostView
from nti.appserver.ugd_edit_views import UGDDeleteView

from nti.contenttypes.presentation.interfaces import ILessonPublicationConstraint
from nti.contenttypes.presentation.interfaces import ILessonPublicationConstraints

from nti.dataserver import authorization as nauth

from nti.dataserver_core.interfaces import ILinkExternalHrefOnly

from nti.externalization.externalization import to_external_object

from nti.externalization.interfaces import LocatedExternalDict
from nti.externalization.interfaces import StandardExternalFields

from nti.links.externalization import render_link

from nti.links.links import Link

CLASS = StandardExternalFields.CLASS
ITEMS = StandardExternalFields.ITEMS
TOTAL = StandardExternalFields.TOTAL
MIMETYPE = StandardExternalFields.MIMETYPE
ITEM_COUNT = StandardExternalFields.ITEM_COUNT

def render_to_external_ref(resource):
	link = Link(target=resource)
	interface.alsoProvides(link, ILinkExternalHrefOnly)
	return render_link(link)

@view_config(context=ILessonPublicationConstraints)
@view_defaults(route_name='objects.generic.traversal',
			   renderer='rest',
			   request_method='GET',
			   permission=nauth.ACT_CONTENT_EDIT)
class LessonPublicationConstraintsGetView(GenericGetView):

	def _do_call(self, constraints):
		result = LocatedExternalDict()
		result[MIMETYPE] = constraints.mimeType
		result[CLASS] = getattr(constraints, '__external_class_name__',
								constraints.__class__.__name__)
		items = result[ITEMS] = []
		for constraint in constraints.Items:
			ext_obj = to_external_object(constraint)
			ext_obj['href'] = render_to_external_ref(constraint)
			items.append(ext_obj)
		result[TOTAL] = result[ITEM_COUNT] = len(items)
		result.__parent__ = self.context
		result.__name__ = self.request.view_name
		result.lastModified = constraints.lastModified
		return result

	def __call__(self):
		return self._do_call(self.context)

@view_config(context=ILessonPublicationConstraints)
@view_defaults(route_name='objects.generic.traversal',
			   renderer='rest',
			   request_method='POST',
			   permission=nauth.ACT_CONTENT_EDIT)
class LessonPublicationConstraintsPostView(UGDPostView):

	content_predicate = ILessonPublicationConstraint.providedBy

	def _do_call(self):
		creator = self.remoteUser
		constraint = self.readCreateUpdateContentObject(creator, search_owner=False)
		constraint.creator = creator.username
		constraint.updateLastMod()

		try:
			validator = ILessonPublicationConstraintValidator(constraint)
			validator.validate()
		except Exception as e:
			raise_json_error(self.request,
							 hexc.HTTPUnprocessableEntity,
							 {
								u'message': str(e),
								u'code': 'ConstraintValidationError',
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
								u'message': str(e),
								u'code': 'ConstraintValidationError',
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
