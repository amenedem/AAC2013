from lib.view import FrontendPage
from lib.view import UploadPage
from google.appengine.api import urlfetch
from google.appengine.api import users
from google.appengine.ext import blobstore
from google.appengine.ext import db
from lib.model import Speaker, Event
from lib.forms import SingleSpeakerForm, SpeakersForm
from lib.cobjects import CEvent, CSpeakerList
from datetime import datetime
import urllib
import json

# This page is displayed in the context of a single event.
# It shows the currently defined speakers for an event and
# allows modification of this list. All of this only if the
# user is logged in and is one of the organizers of the event.
class SpeakersEditPage(FrontendPage):
  def show(self,event_id):
    self.template = 'speakers_edit'
    user = users.get_current_user()
    event = CEvent(event_id).get()
    form = SpeakersForm()
    # check permissions...
    if user and event and (user in event.organizers or users.is_current_user_admin()):
      # get list of event speakers
      speakers = CSpeakerList(event_id).get()
      for s in speakers:
        s.speaker = s.key()
      # we need to store the event
      self.values['event'] = event
      form = SpeakersForm(speakers=speakers)        
    elif not user:
      return self.redirect(
                   users.create_login_url("/event/speakers/edit/" + event_id))
    else:
      return self.redirect("/event/create");
    self.values['current_navigation'] = 'speakers'
    self.values['form_url'] = blobstore.create_upload_url(
                                    '/event/speakers/upload')
    self.values['form'] = form

# process the results uploaded by the user - and then display the edit form
class SpeakersUploadPage(UploadPage):
  def show_post(self):
    self.template = 'speakers_edit'
    user = users.get_current_user()
    event_id = self.request.get('event')
    event = CEvent(event_id).get()
    form = SpeakersForm(self.request.POST)
    # check permissions...
    if user and event and (user in event.organizers or users.is_current_user_admin()):
      if form.validate():
        old_speakers = CSpeakerList(event_id).get()
        for i in range(0,1024):
          prefix = 'speakers-' + str(i) + '-'
          if self.request.get(prefix + 'first_name'):
            # is this a modification of an existing speaker or a new one?
            speaker_id = self.request.get(prefix + 'speaker')
            if speaker_id in [str(s.key()) for s in old_speakers]:
              speaker = [s for s in old_speakers if str(s.key()) == speaker_id][0]
              # delete from old_speaker
              old_speakers = [s for s in old_speakers if str(s.key()) != speaker_id]
            else:
              speaker = Speaker()
            # fill in values for old/new speaker
            speaker.first_name = self.request.get(prefix + 'first_name')
            speaker.last_name = self.request.get(prefix + 'last_name')
            speaker.gplus_id = self.request.get(prefix + 'gplus_id')
            speaker.short_bio = self.request.get(prefix + 'short_bio')
            upload_files = self.get_uploads(prefix + 'thumbnail')
            if len(upload_files) > 0:
              blob_info = upload_files[0]
              speaker.thumbnail = '%s' % blob_info.key()
            speaker.event = event
            # update speaker
            speaker.put()
        # end for
        # now delete all speakers not mentioned yet
        for s in old_speakers:
          s.delete()
        # set info that modification was successful
        self.values['modified_successful'] = True
        # clear cache
        CSpeakerList.remove_from_cache(event_id)
      # set event into form object
      self.values['event'] = event
    elif not user:
      return self.redirect(
                   users.create_login_url("/event/speakers/edit/" + event_id))
    else:
      return self.redirect("/event/create");
    self.values['current_navigation'] = 'speakers'
    self.values['form_url'] = blobstore.create_upload_url(
                                    '/event/speakers/upload')
    self.values['form'] = form
