from lib.view import FrontendPage
from lib.view import UploadPage
from google.appengine.api import urlfetch, blobstore
from google.appengine.api import users
from google.appengine.ext import db
from lib.model import Session, Event, Track, Speaker
from lib.forms import SingleSessionForm, SingleTrackForm, SessionsTracksForm
from lib.cobjects import CEvent, CSessionList, CTrackList, CSpeakerList,\
    CSlotList
from datetime import datetime
import urllib
import json

# helper class for filling in the speakers, slots and tracks in the form
class SessionFormHelper:
  @staticmethod
  def add_speakers(form,speakers):
    # now iterate through the sessions fields in the form
    for session_form in form.sessions.entries:
      session_form.speakers_key.choices = [ (str(sp.key()), sp.first_name + " " + sp.last_name) for sp in speakers ]
      
  @staticmethod
  def add_slots(form,slots):
    # now iterate through the sessions fields in the form
    for session_form in form.sessions.entries:
      session_form.slot_key.choices = [ ("", "Please select slot")] + [ (str(slot.key()), slot.name + " (" + slot.start.strftime('%H:%M') + "-" + slot.end.strftime('%H:%M') + ")") for slot in slots if slot.non_session == False]      

  @staticmethod
  def add_tracks(form,tracks):    
    # now iterate through the sessions fields in the form
    for session_form in form.sessions.entries:
      session_form.track_key.choices = [ ("", "Please select track")] + [ (str(track.key()), track.name) for track in tracks ]      
    
# This page is displayed in the context of a single event.
# It shows the currently defined sessions for an event and
# allows modification of this list. All of this only if the
# user is logged in and is one of the organizers of the event.
class SessionsEditPage(FrontendPage):
  def show(self,event_id):
    self.template = 'sessions_edit'
    user = users.get_current_user()
    event = CEvent(event_id).get()
    form = SessionsTracksForm()
    # check permissions...
    if user and event and (user in event.organizers or users.is_current_user_admin()):
      # get list of event sessions
      sessions = CSessionList(event_id).get()
      for s in sessions:
        s.session = str(s.key())
      # get list of event tracks
      tracks = CTrackList(event_id).get()
      for t in tracks:
        t.track = str(t.key())
      # we need to store the event
      self.values['event'] = event
      form = SessionsTracksForm(sessions=sessions,tracks=tracks)
      speakers = CSpeakerList(event_id).get()
      SessionFormHelper.add_speakers(form,speakers)
      slots = CSlotList(event_id).get()
      SessionFormHelper.add_slots(form, slots)
      SessionFormHelper.add_tracks(form, tracks)
    elif not user:
      return self.redirect(
                   users.create_login_url("/event/sessions/edit/" + event_id))
    else:
      return self.redirect("/event/create");
    self.values['current_navigation'] = 'sessions'
    self.values['form_url'] = blobstore.create_upload_url('/event/sessiontrack/upload')
    self.values['form'] = form

# process the results uploaded by the user - and then display the edit form
class SessionsUploadPage(UploadPage):
  def show_post(self):
    self.template = 'sessions_edit'
    user = users.get_current_user()
    event_id = self.request.get('event')
    event = CEvent(event_id).get()
    form = SessionsTracksForm(self.request.POST)
    # check permissions...
    if user and event and (user in event.organizers or users.is_current_user_admin()):
      # add the speakers for validation
      speakers = CSpeakerList(event_id).get()
      SessionFormHelper.add_speakers(form,speakers)
      slots = CSlotList(event_id).get()
      SessionFormHelper.add_slots(form, slots)    
      tracks = CTrackList(event_id).get()
      for t in tracks:
        t.track = str(t.key())
      SessionFormHelper.add_tracks(form, tracks)      
      
      if form.validate():
        # start with the tracks as they are used by sessions
        for i in range(0,1024):
          prefix = 'tracks-' + str(i) + '-'
          if self.request.get(prefix + 'name'):
            # is this a modification of an existing track or a new one?
            track_id = self.request.get(prefix + 'track')
            if track_id in [t.track for t in tracks]:
              track = [t for t in tracks if t.track == track_id][0]
              # delete from old_session
              tracks = [t for t in tracks if t.track != track_id]
            else:
              track = Track()
            # fill in values for old/new session
            track.name = self.request.get(prefix + 'name')
            track.color = self.request.get(prefix + 'color')
            track.abstract = self.request.get(prefix + 'abstract')
            
            upload_files = self.get_uploads(prefix + 'icon')
            if len(upload_files) > 0:
              blob_info = upload_files[0]
              track.icon = '%s' % blob_info.key()

            track.event_key = event_id
            # update track
            track.put()
        # end for
        # now delete all tracks not mentioned yet
        for t in tracks:
          t.delete()
        CTrackList.remove_from_cache(event_id)
        
        # now the sessions...
        sessions = CSessionList(event_id).get()
        for s in sessions:
          s.session = s.key()
        for i in range(0,1024):
          prefix = 'sessions-' + str(i) + '-'
          if self.request.get(prefix + 'title'):
            # is this a modification of an existing session or a new one?
            session_id = self.request.get(prefix + 'session')
            if session_id in [s.session for s in sessions]:
              session = [s for s in sessions if s.session == session_id][0]
              # delete from session
              sessions = [s for s in sessions if s.session != session_id]
            else:
              session = Session()
            # fill in values for old/new session
            session.title = self.request.get(prefix + 'title')
            session.abstract = self.request.get(prefix + 'abstract')
            session.slot_key = self.request.get(prefix + 'slot_key')
            session.level = self.request.get(prefix + 'level')            
            session.room = self.request.get(prefix + 'room')
            session.track_key = self.request.get(prefix + 'track_key')
            session.live_url = self.request.get(prefix + 'live_url')
            session.youtube_url = self.request.get(prefix + 'youtube_url')
            session.event_key = event_id
            session.speakers_key = self.request.get_all(prefix + 'speakers_key')
            # update session
            session.put()
        # end for
        # now delete all sessions not mentioned yet
        for s in sessions:
          s.delete()
        # set info that modification was successful
        self.values['modified_successful'] = True
        # clear the cache for the event
        CSessionList.remove_from_cache(event_id)        
      # set event into form object
      self.values['event'] = event
    elif not user:
      return self.redirect(
                   users.create_login_url("/event/sessions/edit/" + event_id))
    else:
      return self.redirect("/event/create");
    self.values['current_navigation'] = 'sessions'
    self.values['form_url'] = blobstore.create_upload_url('/event/sessiontrack/upload')
    self.values['form'] = form
