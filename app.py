#!/usr/bin/env python
import web,sys
import markdown
import json
import os
import shutil
import hashlib
import csv
import StringIO
import glob
import uuid
import mimetypes
import httplib2
import time
import datetime
import argparse
import tempfile
import traceback
from pprint import pprint
from os import walk
from os.path import basename
from oauth2client import client
from apiclient.discovery import build
from git import Repo
from git import Git

# Needed for session support
web.config.debug = False

# Session support
web.config.session_parameters['cookie_name'] = 'webpy_session_id'
web.config.session_parameters['cookie_domain'] = 'dss.itksnap.org'
web.config.session_parameters['timeout'] = 31536000 
web.config.session_parameters['ignore_expiry'] = True
web.config.session_parameters['ignore_change_ip'] = True
web.config.session_parameters['secret_key'] = 'Hdx1ym849Zj5Dg3gB8A0'
web.config.session_parameters['expired_message'] = 'Session expired'

# URL mapping
urls = (
  r'/', 'index',
  r"/token", "TokenRequest",
  r"/acceptterms", "AcceptTermsRequest",
  r"/logout", "LogoutPage",
  r"/services", "ServicesPage",
  r"/admin", "AdminPage",
  r"/admintickets", "AdminTicketsPage",
  r"/adminservices", "AdminServicesPage",
  r"/admin/tickets/(\d+)/detail", "AdminTicketsDetailPage",
  r"/about", "AboutPage",
  r"/api/login", "LoginAPI",
  r"/api/oauth2cb", "OAuthCallbackAPI",
  r"/api/token", "TokenAPI",
  r"/api/services", "ServicesAPI",
  r"/api/services/([a-f0-9]+)/detail", "ServicesDetailAPI",
  r"/api/services/([a-f0-9]+)/stats", "ServicesStatsAPI",
  r"/api/tickets", "TicketsAPI",
  r"/api/tickets/(\d+)/files/(input|results)", "TicketFilesAPI",
  r"/api/tickets/(\d+)/files/(input|results)/(\d+)", "TicketFileDownloadAPI",
  r"/api/tickets/(\d+)/status", "TicketStatusAPI",
  r"/api/tickets/(\d+)/log", "TicketLogAPI",
  r"/api/tickets/(\d+)/progress", "TicketProgressAPI",
  r"/api/tickets/(\d+)/queuepos", "TicketQueuePositionAPI",
  r"/api/tickets/(\d+)/detail", "TicketDetailAPI",
  r"/api/tickets/(\d+)/delete", "TicketDeleteAPI",
  r"/api/tickets/(\d+)/retry", "TicketRetryAPI",
  r"/api/tickets/logs/(\d+)/attachments", "TicketLogAttachmentAPI",
  r"/api/pro/services", "ProviderServicesAPI",
  r"/api/pro/services/([\w\-]+)/tickets", "ProviderServiceTicketsAPI",
  r"/api/pro/services/([a-f0-9]+)/claims", "ProviderServiceClaimsAPI",
  r"/api/pro/services/claims", "ProviderMultipleServiceClaimsAPI",
  r"/api/pro/tickets/(\d+)/files/(input|results)", "ProviderTicketFilesAPI",
  r"/api/pro/tickets/(\d+)/files/(input|results)/(\d+)", "ProviderTicketFileDownloadAPI",
  r"/api/pro/tickets/(\d+)/status", "ProviderTicketStatusAPI",
  r"/api/pro/tickets/(\d+)/(error|warning|info|log)", "ProviderTicketLogAPI",
  r"/api/pro/tickets/(\d+)/attachments", "ProviderTicketAttachmentAPI",
  r"/api/pro/tickets/(\d+)/progress", "ProviderTicketProgressAPI",
  r"/api/admin/providers","AdminProvidersAPI",
  r"/api/admin/providers/([\w\-]+)/delete","AdminProviderDeleteAPI", 
  r"/api/admin/providers/([\w\-]+)/users","AdminProviderUsersAPI", 
  r"/api/admin/providers/([\w\-]+)/users/(\d+)/delete","AdminProviderUsersDeleteAPI", 
  r"/api/admin/providers/([\w\-]+)/services","AdminProviderServicesAPI", 
  r"/api/admin/providers/([\w\-]+)/services/([a-f0-9]+)/delete","AdminProviderServicesDeleteAPI", 
  r"/api/admin/tickets/purge/(completed|all)","AdminPurgeTicketsAPI", 
  r"/api/admin/tickets","AdminTicketsAPI", 
  r"/blobs/([a-f0-9]{8})", "DirectDownloadAPI",
  r"/blobs/([a-f0-9]{32})", "DirectDownloadAPI"
  )

# Create the web app
app = web.application(urls, globals())

# Connect to the database
db = web.database(
  host=os.environ['POSTGRES_PORT_5432_TCP_ADDR'],
  port=os.environ['POSTGRES_PORT_5432_TCP_PORT'],
  dbn='postgres', 
  db=os.environ['ALFABIS_DATABASE_NAME'],
  user=os.environ['ALFABIS_DATABASE_USERNAME'],
  pw=os.environ['ALFABIS_DATABASE_PASSWORD'])

# Configure the session. By default, the session is initialized with nothing
# but in no-auth mode, the session should be initialized as logged in with
# user set 
if "ALFABIS_NOAUTH" not in os.environ:

  # Blank session
  sess = web.session.Session(
    app, web.session.DBStore(db, 'sessions'), 
    initializer={'loggedin': False, 'acceptterms': False, 'is_admin': False})

else:
  # Make sure user exists, if not populate in the user table
  new_token=os.urandom(24).encode('hex')
  db.query(
    "insert into users values(DEFAULT,'test@example.com',$new_token,"
    "                         'Test User', TRUE, 'poweruser') "
    "on conflict do nothing", vars=locals())

  # Get the user id of the test user
  user_id = db.select('users', where="email='test@example.com'")[0].id;

  # Prepopulated session
  sess = web.session.Session(
    app, web.session.DBStore(db, 'sessions'), 
    initializer={'loggedin': True, 'acceptterms': True, 'is_admin': True,
                 'email' : 'test@example.com', 'user_id' : user_id})




# Configure the template renderer with session support
render = web.template.render(
  'temp/', 
  globals={'markdown': markdown.markdown, 'session': sess}, 
  cache=False);

# Configure the markdown to HTML converter (do we need this really? Why not HTML5?)
md = markdown.Markdown(output_format='html4',
    extensions = ['markdown.extensions.meta',
                  'markdown.extensions.tables'])

# A function to render a markdown template with parameters
def render_markdown(page, *args):
  # Render the page requested into a string
  text = getattr(render, page)(*args);

  # A context dict for menu rendering
  ctx = {}
  ctx['admin'] = web.ctx.path.startswith('/admin')
  ctx['path'] = web.ctx.path

  # Render the full page
  return render.style(md.convert(unicode(text)), ctx);

# Render markdown page without menus
def render_markdown_nomenus(page, *args):
  # Render the page requested into a string
  text = getattr(render, page)(*args);

  # A context dict for menu rendering
  ctx = {}
  ctx['admin'] = web.ctx.path.startswith('/admin')
  ctx['path'] = web.ctx.path

  # Render the full page
  return render.bare(md.convert(unicode(text)), ctx);

# Determine mime type from filename or return octet stream
def guess_mimetype(filename):
  if mimetypes.inited is False:
    mimetypes.init()
  mime_type = mimetypes.guess_type(filename)[0]
  if mime_type is None:
    mime_type="application/octet-stream"
  return mime_type

# This class facilitates working with the Google OAuth2 API
class OAuthHelper:

  def __init__(self):

    self.flow = client.flow_from_clientsecrets(
        os.environ['ALFABIS_GOOGLE_CLIENTSECRET'],
        scope=[
            'https://www.googleapis.com/auth/userinfo.email',
            'https://www.googleapis.com/auth/userinfo.profile'],
        redirect_uri=web.ctx.home+"/api/oauth2cb")

  def auth_url(self):
    return self.flow.step1_get_authorize_url()

  def authorize(self, auth_code):

    # Obtain credentials from the auth code
    self.credentials = self.flow.step2_exchange(auth_code)

    # Get use information from Google
    self.http_auth = self.credentials.authorize(httplib2.Http())
    user_info_service = build('oauth2','v2',http=self.http_auth)
    user_info = user_info_service.userinfo().get().execute()

    return user_info

# Single function to check whether the user is logged in
def is_logged_in():
  return sess.loggedin

def is_logged_in_as_admin():
  return sess.loggedin and sess.is_admin

# Print session contents 
def print_session():
  print("*** Session Info ***")
  print("  sess.loggedin = %d" % sess.loggedin)
  print("  sess.is_admin = %d" % sess.is_admin)
  print("  sess.email = %s" % sess.email)
  print("  sess.acceptterms= %d" % sess.acceptterms)

# Home Page handler
class index:
  def GET(self):

    # Create the URL for authorization
    auth_url=None
    if is_logged_in() == False:
      auth_url = OAuthHelper().auth_url()

    # The redirect URL for after authentication
    sess.return_uri=web.ctx.home
    return render_markdown("hohum", False, None, auth_url)

# Handler for accepting terms of service
class AcceptTermsRequest:
  def POST(self):
    if 'cb' in web.input() and web.input().cb == 'on':
      sess.acceptterms = True
      raise web.seeother("/token")
    else:
      sess.acceptterms = False
      raise web.seeother("/logout")

# Token request handler
class TokenRequest:

  def GET(self):

    # Create the URL for authorization
    auth_url=None
    token=None
    if is_logged_in() == False:
      auth_url = OAuthHelper().auth_url()
    else:
      email = sess.email
      res = db.select('users', where="email=$email", vars=locals())
      token=res[0].passwd

    # Get the user to accept the terms of service
    sess.return_uri=web.ctx.home + "/token"
    return render_markdown("token", auth_url, token)


# API-based token request: only works if you are already logged in
class TokenAPI:

  def GET(self):

    # Must be logged in and accepted terms, otherwise you have to use the web page
    if is_logged_in() is False or sess.acceptterms is False:
      raise web.HTTPError("401 unauthorized", {}, "Unauthorized access")

    # Retrieve the token
    email = sess.email
    res = db.select('users', where="email=$email", vars=locals())
    token=res[0].passwd

    # Return token
    return token

class LogoutPage:

  def GET(self):
    sess.kill()
    raise web.seeother('/')

class ServicesPage:

  def GET(self):
    
    # We must be logged in, but not much else
    if is_logged_in() is not True:
      raise web.seeother("/")

    web.header('Cache-Control','no-cache, no-store, must-revalidate')
    web.header('Pragma','no-cache')
    web.header('Expires', 0)

    # Get a listing of services with details
    services = db.query(
      "select name, shortdesc, githash, json, now() - pingtime as since, "
      "       D.avg as avg_runtime, n_success, n_failed, "
      "       greatest(0,W.count) as queue_length "
      "from services S "
      "     left join ( "
      "         select service_githash, avg(runtime) "
      "         from success_ticket_duration "
      "         where now() - endtime < interval '1 day' "
      "         group by service_githash "
      "     ) D on S.githash = D.service_githash "
      "     left join ( "
      "         select service_githash, "
      "                greatest(0,sum(cast (TH.status = 'success' as int))) as n_success, "
      "                greatest(0,sum(cast (TH.status in ( 'failed', 'timeout') as int))) as n_failed "
      "         from ticket_history TH, tickets T "
      "         where TH.ticket_id = T.id  and now() - atime < interval '1 day' "
      "         group by service_githash "
      "     ) Q on Q.service_githash = githash "
      "     left join ( "
      "         select service_githash, count(id) "
      "         from tickets where status='ready' group by service_githash "
      "     ) W on W.service_githash = githash "
      "where S.current = true "
      "order by n_success desc");

    # Parse through the results into something more readable
    serv_data = []
    for x in services:
      s = {}
      j = json.loads(x.json)
      s['name'] = x.name
      s['shortdesc'] = x.shortdesc;
      s['longdesc'] = j['longdesc'];
      s['url'] = j['url'];
      alive_sec = x.since.total_seconds();
      s['alive_btn'] = 'green' if alive_sec < 600 else ('yellow' if alive_sec < 3600 else 'red')
      s['alive_min'] = round(alive_sec / 60,2)

      n_s = x.n_success if x.n_success is not None else 0
      n_f = x.n_failed if x.n_failed is not None else 0

      if n_s + n_f == 0:
        s['srate_btn'] = "cyan"
        s['srate_tooltip'] = "No tickets completed in the last 24 hours"
      else:
        err_rate = n_f * 1.0 / (n_s + n_f)
        s['srate_btn'] = "green" if err_rate < 0.1 else ("yellow" if err_rate < 0.2 else "red")
        s['srate_tooltip'] = "Success: %d, Failed: %d, Error Rate: %f" % (n_s, n_f, err_rate)

      ql = x.queue_length
      s['queuelen_btn'] = "cyan" if ql == 0 else ("green" if ql < 5 else ("yellow" if ql < 25 else "red"))
      s['queuelen'] = x.queue_length

      if x.avg_runtime is not None:
        s['runtime'] = "<br>%4.1f min" % (x.avg_runtime.total_seconds() / 60.0)
      else:
        s['runtime'] = ""

      serv_data.append(s)

    return render_markdown("services_home", serv_data)



class AdminPage:

  def GET(self):
    
    # We must be logged in, but not much else
    if is_logged_in_as_admin() is not True:
      raise web.HTTPError("401 unauthorized", {}, "Unauthorized access")

    return render_markdown("admin")


class AdminTicketsPage:

  def format_date(self, dt):

    n = datetime.datetime.now()
    if n.year == dt.year:
      if n.day == dt.day:
        return dt.strftime("%H:%M");
      return dt.strftime("%b %d  %H:%M");
    return dt.strftime("%b %d %Y  %H:%M");

  def format_delta(self, dt1, dt2):

    if dt1 is None or dt2 is None:
      return None

    delta = dt2 - dt1
    h = delta.seconds / 3600
    m = (delta.seconds / 60) % 60
    s = delta.seconds % 60

    if h > 0:
      return "%02d:%02d:%02d" % (h,m,s)
    else:
      return "%02d:%02d" % (m,s)


  def GET(self):

    # We must be logged in, but not much else
    if is_logged_in_as_admin() is not True:
      raise web.HTTPError("401 unauthorized", {}, "Unauthorized access")

    # Get the listing of tickets, this is a hell of a query
    q = db.query(
        "select T.id, S.name, T.status, email, dispname, "
        "       Tinit, Tclaimed, Tsuccess, Tfailed, Ttimeout, Tdeleted, progress "
        "from tickets T "
        "     left join users U on T.user_id = U.id "
        "     left join services S on T.service_githash = S.githash "
        "     left join (select ticket_id, "
        "                       max(case when status='init' then atime else NULL end) as Tinit, "
        "                       max(case when status='claimed' then atime else NULL end) as Tclaimed, "
        "                       max(case when status='success' then atime else NULL end) as Tsuccess, "
        "                       max(case when status='failed' then atime else NULL end) as Tfailed, "
        "                       max(case when status='timeout' then atime else NULL end) as Ttimeout, "
        "                       max(case when status='deleted' then atime else NULL end) as Tdeleted "
        "                from ticket_history group by ticket_id) TH on TH.ticket_id = T.id "
        "     left join (select ticket_id, sum(progress * (chunk_end - chunk_start)) as progress "
        "                from ticket_progress group by ticket_id) P on P.ticket_id = T.id "
        "order by T.id desc limit 100")

    # Send this query to the web page
    tix_data=[]
    for row in q:
      
      # Orgaize the data for this ticket
      T = {}
      print row
      T['id'] = row.id
      T['service'] = row.name
      T['status'] = row.status

      # If the status is 'deleted', show the last useful status
      if row.status == 'deleted':
        T['deleted'] = True
        T['status'] = 'failed' if row.tfailed is not None else (
          'timeout' if row.ttimeout is not None else (
            'success' if row.tsuccess is not None else 'aborted'))
      else:
        T['deleted'] = False
        T['status'] = row.status
                          
      T['status_color'] = 'darkred' if T['status'] in ('failed','timeout') else (
        'darkgreen' if T['status'] == 'success' else (
          'goldenrod' if T['status'] == 'aborted' else 'gray'))
                          
      T['email'] = row.email
      T['dispname'] = row.dispname
      if len(T['dispname']) == 0:
        T['dispname'] = T['email']
      
      T['T_init'] = self.format_date(row.tinit)
      T['T_claim'] = self.format_delta(row.tinit, row.tclaimed)

      # Figure out the end date
      t_end = datetime.datetime.now();
      for t_test in (row.tsuccess, row.tfailed, row.ttimeout, row.tdeleted):
        if t_test is not None and t_test < t_end:
          t_end = t_test

      T['T_end'] = self.format_delta(row.tclaimed, t_end)
      T['progress'] = row.progress
      


      tix_data.append(T)

    return render_markdown("admin_tickets", tix_data)


class AdminTicketsDetailPage:

  def GET(self, ticket_id):

    # We must be logged in, but not much else
    if is_logged_in_as_admin() is not True:
      raise web.HTTPError("401 unauthorized", {}, "Unauthorized access")

    # Get the detail using the API
    qr = TicketLogic(ticket_id).get_detail()

    # Get formatted JSON
    ticket_json = json.dumps(qr, default=my_json_converter, indent=4)

    # Render the page
    return render_markdown_nomenus("admin_ticket_detail", ticket_id, ticket_json)


class AdminServicesPage:

  def GET(self):

    # We must be logged in, but not much else
    if is_logged_in_as_admin() is not True:
      raise web.HTTPError("401 unauthorized", {}, "Unauthorized access")

    # Query the list of providers
    r_prov = db.select('providers', where='current is true', vars=locals())

    # Create a dictionary of providers
    pd = {}

    # Go through query filling out provider info
    for row_prov in r_prov:

      # The name of the current provider
      p_id = row_prov.name
      
      # Dictionary for this provider
      pd[p_id] = {}

      # Query the list of services for this provider
      r_serv = db.query(
        "select A.name, A.version, A.githash from services A, provider_services B "
        "where A.githash = B.service_githash and B.current is TRUE and A.current is TRUE "
        "      and B.provider_name = $p_id "
        "order by A.name, A.version", vars = locals())

      pd[p_id]['services'] = query_as_array_of_dict(r_serv, ['name','version','githash'])

      # Query the list of users for this provider
      r_users = db.query(
        "select email,id,dispname,admin from users A, provider_access B "
        "where A.id = B.user_id and B.provider=$p_id "
        "order by email", vars=locals())

      pd[p_id]['users'] = query_as_array_of_dict(r_users, ['email', 'id', 'dispname', 'admin'])

    return render_markdown("admin_services", pd)






class AboutPage:

  def GET(self):
    
    return render_markdown("about")

# ======================
# Business Logic classes
# ======================

# Logic around tickets. This class is initialized around the ticket ID
class TicketLogic:

  def __init__(self, ticket_id):
    self.ticket_id = ticket_id

  def check_consumer_access(self, user_id, status_list = None):
    res = db.select("tickets",where="user_id=$user_id and id=$self.ticket_id",vars=locals())
    return len(res) > 0 and (status_list is None or res[0].status in status_list)

  def check_provider_access(self, provider_id, status_list = None):
    res = db.query(
      "select T.id, T.status from tickets T, provider_access PA, provider_services PS "
      "where T.id = $self.ticket_id and PA.user_id = $provider_id "
      "  and T.service_githash = PS.service_githash and PA.provider = PS.provider_name",
      vars=locals())
    return len(res) > 0 and (status_list is None or res[0].status in status_list)

  def is_not_deleted(self):
    res = db.select("tickets",where="id=$self.ticket_id", vars=locals())
    return len(res) > 0 and (res[0].status != 'deleted')

  # Check that the specified provider has actually claimed this ticket 
  def check_provider_claimed(self, user_id):
    res = db.select("claim_history", 
      where="ticket_id=$self.ticket_id and puser_id=$user_id",
      vars=locals());
    return len(res) > 0

  # Set the status of the ticket. This sets the status in the 'tickets' table but
  # also logs the status change in the 'ticket_history' table
  def set_status(self, new_status):

    with db.transaction():

      # Set the status of the ticket in the database
      db.update("tickets", where="id = $self.ticket_id", status = new_status, vars=locals())

      # Insert the history entry
      db.insert("ticket_history", ticket_id = self.ticket_id, status = new_status);

      # Return the new status
      return db.select("tickets", where="id=$self.ticket_id", vars=locals())[0].status;


  # Add a message to the ticket log
  def append_log(self, category, message):

    log_id = None

    # This requires a transaction
    with db.transaction():

      # Create a log entry for this ticket
      log_id = db.insert("ticket_log",
        ticket_id=self.ticket_id, category=category, message=message)

      # Assign all unfiled attachments to this log message
      db.query(
        "insert into ticket_log_attachment "
        "  select $log_id,A.id from ticket_attachment as A "
        "    left join ticket_log_attachment as B on A.id = B.attachment_id "
        "    where ticket_id = $self.ticket_id and B.log_id is null",
        vars=locals())

    # Find all the unassigned attachments for this ticket
    return log_id

  # Query logs - returns a database result
  def get_logs(self, start_id):

    return db.query(
        "select L.*,count(B.attachment_id) as attachments "
        "  from ticket_log L left join ticket_log_attachment B on L.id = B.log_id "
        "  where ticket_id = $self.ticket_id and id > $start_id group by L.id,log_id"
        "  order by atime",
        vars=locals());

  # Measure the total progress for a ticket
  def total_progress(self):
    res = db.query(
      "select greatest(0, sum((chunk_end-chunk_start) * progress)) as x from ticket_progress "
      "where ticket_id=$self.ticket_id", 
      vars=locals())
    if len(res) > 0:
      return float(res[0].x)
    else:
      return 0

  # Measure the total progress for a ticket
  def queue_position(self):
    res = db.query(
      "select count(id) as x from tickets "
      "where service_githash = (select service_githash from tickets where id = $self.ticket_id) "
      "  and status='ready' "
      "  and id <= $self.ticket_id", 
      vars=locals())
    if len(res) > 0:
      return res[0].x

  # Update the progress of a ticket for a chunk
  def set_chunk_progress(self, chunk_start, chunk_end, progress):
    with db.transaction():

      # Update the ping on this service
      db.query(
        "update services as S set pingtime=now() "
        "from tickets as T "
        "where S.githash = T.service_githash and T.id = $self.ticket_id", vars=locals());

      # Try to update the progress line
      n = db.update("ticket_progress", 
        where="ticket_id = $self.ticket_id and chunk_start=$chunk_start and chunk_end=$chunk_end", 
        progress = progress, vars=locals())

      # If nothing got updated, this means we need to insert
      if n == 0:
        db.insert("ticket_progress", 
          ticket_id=self.ticket_id, chunk_start=chunk_start,
          chunk_end=chunk_end, progress=progress)

  # Get the file directory for given area
  def get_filedir(self, area):
    filedir = 'datastore/tickets/%08d/%s' % (int(self.ticket_id), area)
    if not os.path.exists(filedir):
      os.makedirs(filedir)
    return filedir

  # List all the files associated with ticket in a given area
  def list_files(self, area):

    # List all of the files
    filedir = self.get_filedir(area)

    # Send the directory contents as CSV
    return directory_as_csv(filedir)

  # Erase the ticket file directory
  def erase_dir(self, area):
    filedir = 'datastore/tickets/%08d/%s' % (int(self.ticket_id), area)
    if os.path.exists(filedir):
      shutil.rmtree(filedir)

  # Erase the attachments for a ticket
  def erase_attachments(self):
    filedir = 'datastore/attachments/%08d' % int(self.ticket_id)
    if os.path.exists(filedir):
      shutil.rmtree(filedir)

  # Receive uploaded files associated with a ticket and area
  def receive_file(self, area, fileobj):

    # Get the directory to store this in
    filedir = self.get_filedir(area)
    filepath=fileobj.filename.replace('\\','/') # replaces the windows-style slashes with linux ones.
    filename=filepath.split('/')[-1] # splits the and chooses the last part (the filename with extension)
    
    fout = open(filedir +'/'+ filename,'w') # creates the file where the uploaded file should be stored
    fout.write(fileobj.file.read()) # writes the uploaded file to the newly created file.
    fout.close() # closes the file, upload complete.

    # Return the local path to file
    return filename

  # Serve file from given area
  def get_nth_file(self, area, file_index):

    # Get the ticket directory
    filedir = self.get_filedir(area)

    # Get the specified file
    filename = get_indexed_file(filedir, int(file_index))
    if filename is None:
      return self.raise_badrequest("File %s does not exist for ticket %d" % file_index,self.ticket_id)

    return filename

  # Delete the ticket
  def delete_ticket(self):

    # Mark the ticket as having been deleted
    new_status = self.set_status("deleted")

    # Empty the directory for this ticket (in case it exists from a previous DB)
    for area in ('input','results'):
      self.erase_dir(area)

    # Clear the attachments
    self.erase_attachments()

    return new_status

  # Retry ticket
  def retry(self):

    # Mark the ticket as being ready again
    new_status = self.set_status("ready")

    # Empty the results directory for the ticket (just in case)
    self.erase_dir("results")

    # Make a log entry
    self.append_log("info", "Retrying ticket")

    # Return the new status
    return new_status

  # Create an attachment entry in the database and get ready to upload attachment
  def add_attachment(self, desc, filename, mime_type = None):

    # Create a new hash for the attachment
    ahash = uuid.uuid4().hex

    # Check for mime type
    if mime_type is None:
      mime_type = guess_mimetype(filename)

    # Insert the entry into log_attachment
    res = db.insert("ticket_attachment", ticket_id=self.ticket_id, 
        description=desc, mime_type=mime_type, uuid = ahash)

    # Create the directory for the attachment
    filedir = 'datastore/attachments/%08d' % int(self.ticket_id)
    if not os.path.exists(filedir):
      os.makedirs(filedir)

    # Create the new filename based on the hash
    filebase = basename(filename)
    fullext = filebase[filebase.find('.'):]
    newname = ahash + fullext;

    # Create the filename where this attachment will be stored
    afile = filedir +'/'+ newname

    # Return a tuple of dbindex, hash, and filename
    return (res, ahash, afile)

  # Get ticket detail in a JSON-dumpable structure
  def get_detail(self):

    # Initialize the query result
    qr = {}

    # Get the status of this ticket
    qr['status'] = db.select('tickets', where='id=$self.ticket_id', vars=locals())[0].status;

    # Depending on status, assign progress
    if qr['status'] == 'claimed':
      qr['progress'] = float(TicketLogic(self.ticket_id).total_progress())
    elif qr['status'] in ('failed','success','timeout'):
      qr['progress'] = 1.0
    else:
      qr['progress'] = 0.0

    # If the status is 'ready', report the queue position (global)
    if qr['status'] == 'ready':
      qresult = db.query(
        "select count(*) from tickets where status='ready' and id <= $self.ticket_id", 
        vars=locals())
      qr['queue_position'] = qresult[0].count

    # User can request partial update since given log_id
    start_id=0
    if "since" in web.input():
      start_id=web.input().since

    # Get the logs for this ticket
    qresult = TicketLogic(self.ticket_id).get_logs(start_id)

    # Convert this query to an array
    logs = query_as_array_of_dict(qresult, ['id','atime','category','attachments','message'])

    # For each entry in the log array, get its attachments
    for log_entry in logs:
      if log_entry['attachments'] > 0:
        qresult = TicketLogLogic(log_entry['id']).get_attachments()
        log_entry['attachments'] = query_as_array_of_dict(qresult, ['id','description','mime_type','url'])
      else:
        log_entry['attachments'] = []

    # Store the logs
    qr['log'] = logs

    return qr


# Logic around ticket log messages. 
class TicketLogLogic:

  def __init__(self, log_id):
    self.log_id = log_id

  def check_provider_access(self, provider_id, state_list = None):
    # Get the ticket id
    res = db.select('ticket_log',where="id=$self.log_id")
    if len(res) != 1:
      raise_badrequest('Invalid log id')
    
    # Check access to the the ticket
    TicketLogic(res[0].ticket_id).check_provider_access(provider_id)

    # Check the states
    return (state_list is None or res[0].state in state_list)

  def check_consumer_access(self, user_id):

    res = db.query(
      "select L.id from ticket_log L, tickets T "
      "where T.user_id = $user_id and T.id = L.ticket_id and L.id = $self.log_id",
      vars=locals())

    return len(res) > 0

  # List all attachments for this log entry with URLs
  def get_attachments(self):

    urlbase = web.ctx.home + '/blobs/'
    return db.query(
      "select id,description,mime_type,$urlbase || substr(uuid,0,9) as url "
      "  from ticket_attachment A left join ticket_log_attachment B "
      "    on A.id = B.attachment_id "
      "  where B.log_id = $self.log_id order by id",
      vars=locals());

  # Create an attachment entry in the database and get ready to upload attachment
  def add_attachment(self, desc, filename, mime_type = None):

    # Create a new hash for the attachment
    ahash = uuid.uuid4().hex

    # Check for mime type
    if mime_type is None:
      mime_type = guess_mimetype(filename)

    # Create a database entry
    with db.transaction():
      
      # Insert the entry into log_attachment
      res = db.insert("ticket_log_attachment", log_id=self.log_id, 
        description=desc, mime_type=mime_type, uuid = ahash)

      # Get the number of attachments
      res2 = db.query(
        "select count(id) from ticket_log_attachment "
        "where log_id = $self.log_id", vars=locals())

      # Update the attachment count
      db.update("ticket_log", where="id = $self.log_id", attachments=res2[0].count, vars=locals())

    # Create the directory for the output
    filedir = 'datastore/logdata/%08d' % int(self.log_id)
    if not os.path.exists(filedir):
      os.makedirs(filedir)

    # Create the new filename based on the hash
    filebase = basename(filename)
    fullext = filebase[filebase.find('.'):]
    newname = ahash + fullext;

    # Create the filename where this attachment will be stored
    afile = filedir +'/'+ newname

    # Return a tuple of dbindex, hash, and filename
    return (res, ahash, afile)

  # Change the status of the log entry
  def set_status(self, status):

    return db.update("ticket_log", where="id = $self.log_id", state = status, vars=locals())

# Logic around providers and services (which providers offer which service, etc)
class ProviderServiceLogic:

  # Check for any services that do not have a provider and mark them not current
  def clean_orphaned_services(self):
    
    # Get a list of service githashshes and whether the service has any providers
    q = db.query(
      "select S.githash, bool_or(PS.current) as any_prov "
      "from provider_services PS, services S "
      "where S.githash=PS.service_githash "
      "GROUP BY S.githash", vars=locals())

    # For each service that has been 'orphaned', disable it
    for qrow in q:
      if qrow.any_prov is False:
        db.update("services", where="githash=$qrow.githash", current=False, vars=locals())


# Logic around claiming tickets and scheduling
class ClaimLogic:

  def __init__(self, user_id, provider_name, provider_code):
    (self.user_id, self.provider_name, self.provider_code) = (user_id, provider_name, provider_code)

  def claim_multiservice(self, service_githash_list):

    # Put the services back together into a SQL passable string
    svc_sql =  ",".join("'{0}'".format(w) for w in service_githash_list)

    with db.transaction():

      # Update the ping on all services
      db.query("update services set pingtime=now() where githash in (%s)" % svc_sql)

      # Do the SQL call to find the service to use.
      # TODO: we need some sort of a fair scheduling scheme. The current scheme is 
      # pretty ridiculous
      res = db.query(
        "select id from tickets "
        "where service_githash in (%s) "
        "  and status = 'ready' "
        "order by id asc limit 1" % svc_sql)

      # Nothing returned? Means there are no ready tickets
      if len(res) == 0:
        return None

      # Now we have a ticket
      ticket_id = res[0].id
      tl = TicketLogic(ticket_id)

      # Make an entry in the claims table, to keep track of this claim
      db.insert("claim_history", 
                ticket_id=ticket_id, 
                provider=self.provider_name, 
                provider_code=self.provider_code,
                puser_id=self.user_id)

      # Mark the ticket as claimed
      tl.set_status("claimed")

      # Update the log for the user
      tl.append_log("info", "Ticket claimed by provider %s instance %s" 
                    % (self.provider_name,self.provider_code))

      # Return the ticket id and service hash
      return db.select("tickets", where="id=$ticket_id", vars=locals())


# Logic around services. This class is initialized with a service ID
class ServiceLogic:

  def __init__(self, service_githash):
    self.service_githash = service_githash

  def check_provider_access(self, user_id):
    res = db.query(
      "select * from provider_access PA, provider_services PS "
      "where PS.service_githash=$self.service_githash "
      "  and PS.provider_name = PA.provider"
      "  and user_id = $user_id",
      vars=locals());
    return len(res) > 0

  def claim_ticket(self, user_id, provider_name, provider_code):

    # Create a transaction because this operation must be atomic
    with db.transaction():

      # Update the ping on this service
      db.query("update services set pingtime=now() where githash = $self.service_githash", vars = locals());

      # Get the highest priority 'ready' ticket. TODO: For now the priority is just based
      # on the ticket serial number, but this will need to be updated to use an actual
      # prioritization system in the future
      res = db.query(
          "select T.id from tickets T "
          "where T.service_githash = $self.service_githash "
          "  and T.status = 'ready' "
          "order by T.id asc limit 1", vars=locals());

      # Nothing returned? Means there are no ready tickets
      if len(res) == 0:
        return None

      # Now we have a ticket
      ticket_id = res[0].id

      # Make an entry in the claims table, to keep track of this claim
      db.insert("claim_history", 
                ticket_id=ticket_id, 
                provider=provider_name, 
                provider_code=provider_code,
                puser_id=user_id)

      # Mark the ticket as claimed
      TicketLogic(ticket_id).set_status("claimed")

      # Update the log for the user
      TicketLogic(ticket_id).append_log("info",
          "Ticket claimed by provider %s instance %s" % (provider_name,provider_code))

      # Return the ticket ID
      return ticket_id


# =====================
# RESTful API
# =====================

def my_json_converter(o):
    if isinstance(o, datetime.datetime):
        return o.__str__()
    if isinstance(o, datetime.timedelta):
        return o.__str__()

def query_as_array_of_dict(qresult, fields):
  darray = []
  for row in qresult:
    drow = {}
    for field in fields:
      drow[field] = row[field]
    darray.append(drow)
  return darray;

def query_as_json(qresult, fields):
  darray = query_as_array_of_dict(qresult, fields)
  return json.dumps({"result" : darray}, default=my_json_converter)

def query_as_csv(qresult, fields):
  strout = StringIO.StringIO()
  csvout = csv.DictWriter(strout, fieldnames=fields, extrasaction='ignore')
  csvout.writerows(qresult)
  return strout.getvalue()

def query_as_reqfmt(qresult, fields):
  if 'format' in web.input() and web.input().format == 'json':
    web.header('Content-Type','application/json')
    return query_as_json(qresult, fields)
  else:
    web.header('Content-Type','text/csv')
    return query_as_csv(qresult, fields)

def directory_as_csv(dir_path):
  files = filter(os.path.isfile, glob.glob(dir_path + "/*"))
  files.sort(key=lambda x: os.path.getmtime(x))
  table = [(i,os.path.basename(files[i])) for i in range(len(files))]
  strout = StringIO.StringIO()
  csvout = csv.writer(strout)
  csvout.writerows(table)
  return strout.getvalue()

def get_indexed_file(dir_path, index):
  files = filter(os.path.isfile, glob.glob(dir_path + "/*"))
  files.sort(key=lambda x: os.path.getmtime(x))
  if index >= 0 and index < len(files):
    return files[index]


class AbstractAPI(object):

  # Check if the user is authorized to be here
  def check_auth(self):
    if is_logged_in() is False:
      self.raise_unauthorized("You are not logged in!")

  # Raise an unauthorized error with a message
  def raise_unauthorized(self, message = "unauthorized"):
    raise web.HTTPError("401 unauthorized", {}, message)

  # Raise an unauthorized error with a message
  def raise_badrequest(self, message = "bad request"):
    raise web.HTTPError("400 bad request", {}, message)

  # Get the githash of the requested service, either by name or by githash
  def get_service_githash(self):

    # If githash specified, we are done
    if 'githash' in web.input():
      return web.input().githash

    # If name specified, find the latest service
    if 'name' in web.input():
      name = web.input().name
      qresult = db.query(
        "select to_number(split_part(version,'.',1),'999') as major, "
        "       to_number(split_part(version,'.',2),'999') as minor, "
        "       to_number(split_part(version,'.',3),'999') as patch, "
        "       githash from services where name=$name "
        "order by major desc,minor desc,patch desc limit 1", vars=locals());
      if len(qresult) == 1:
        return qresult[0].githash
      else:
        self.raise_badrequest("Unable to find service named %s" % name)

    # What do we do?
    self.raise_badrequest("Unable to find service: neither name nor githash specified")


class OAuthCallbackAPI:
  
  def GET(self):

    # Get the code from callback
    auth_code = web.input().code

    # Authorize via code
    user_info = OAuthHelper().authorize(auth_code)

    # Get the email
    email = user_info.get("email")
    alfabis_id=None

    # Create an account for the user with credential information
    res = db.select('users', where="email=$email", vars=locals())
    if len(res) > 0:
      stored_user_data = res[0]
      alfabis_id = stored_user_data.id
      is_admin = stored_user_data.sysadmin
    else:
      passwd=os.urandom(24).encode('hex')
      print user_info
      alfabis_id = db.insert('users', email=email, passwd=passwd, dispname=user_info.get("name"))
      is_admin = False

    # Set the user information in the session
    sess.email = user_info.get('email')
    sess.name = user_info.get('name')
    sess.user_id = alfabis_id
    sess.is_admin = is_admin
    sess.loggedin = True

    # Redirect to the home page
    raise web.seeother(sess.return_uri)
    

class LoginAPI (AbstractAPI):

  def response(self):
    if 'format' in web.input() and web.input().format == 'json':
      return json.dumps({ 'result': {'email' : sess.email} })
    else:
      return ("logged in as %s \n" % sess.email);

  def GET(self):
    self.check_auth()
    return self.response()

  def POST(self):

    # Get the email and password of the user
    # try:
    token = web.input().token
    res = db.select('users', where='passwd=$token', vars=locals())

    if len(res) > 0:
      user_data = res[0];
      sess.loggedin = True
      sess.user_id = user_data.id
      sess.email = user_data.email
      sess.is_admin = user_data.sysadmin

      # Now that the user has used the token, generate a new token (so that there
      # is no security risk from sharing tokens)
      new_token=os.urandom(24).encode('hex')
      db.update("users", where="passwd=$token", passwd = new_token, vars=locals())

      return self.response()

    else:
      sess.kill();
      raise web.unauthorized()

    #except:
    #  raise web.badrequest()

class ServicesAPI (AbstractAPI):

  def GET(self):
    
    self.check_auth()

    qresult = db.select("services", where='current=true');
    return query_as_reqfmt(qresult, ['name','githash','version','shortdesc'])


class ServicesDetailAPI (AbstractAPI):

  def GET(self, githash):
    
    self.check_auth()

    qresult = db.select("services", where="githash=$githash",vars=locals())
    if len(qresult) == 0:
      self.raise_badrequest("Service %s is not available" % githash)
    json = qresult[0].json
    web.header('Content-Type','application/json')
    return json


class ServicesStatsAPI (AbstractAPI):

  def GET(self, githash):

    self.check_auth()

    # try:

    # The dictionary for the statistics
    retval = {}

    # Get the number of successful and failed tickets in the last 24 hours
    q1 = db.query(
      "select greatest(0,sum(cast (TH.status = 'success' as int))) as n_success, "
      "       greatest(0,sum(cast (TH.status in ( 'failed', 'timeout') as int))) as n_failed "
      "from ticket_history TH, tickets T where TH.ticket_id = T.id "
      "     and now() - atime < interval '24 hours' "
      "     and service_githash = $githash", vars=locals())[0];

    retval['n_success'] = q1.n_success
    retval['n_failed'] = q1.n_failed

    # Get the average ticket duration
    if retval['n_success'] > 0:
      q2 = db.query(
        "select avg(runtime) as avg_duration "
        "from success_ticket_duration "
        "where service_githash = $githash "
        "      and now() - endtime < interval '24 hours'", vars=locals());

      retval['avg_duration'] = q2[0].avg_duration

    # Get the last time we heard from this service
    q3 = db.query(
      "select now() - pingtime as deltat "
      "from services where githash=$githash", vars=locals());
    retval['last_heard_from'] = q3[0].deltat

    # Get the size of the queue for this service (all tickets in ready state)
    q4 = db.query(
      "select count(id) from tickets "
      "where service_githash=$githash "
      "      and status = 'ready'", vars=locals());
    retval['queue_length'] = q4[0].count

    # Return the results in requested format
    print retval
    return query_as_reqfmt([retval], retval.keys())
      

    #except:
    #  self.raise_badrequest("Error getting statistics for service %s")



class TicketsAPIBase(AbstractAPI):

  # Make sure that the user has access to this particular
  # ticket. This also makes sure that the used is logged in
  def check_ticket_access(self, ticket_id, status_list = None):
    
    # Make sure we are actually logged in
    self.check_auth()

    # Check if the ticket belongs to this user
    if sess.is_admin is not True and TicketLogic(ticket_id).check_consumer_access(sess.user_id, status_list) is False:
      self.raise_badrequest("Ticket %s not found for user %s" % (ticket_id,sess.user_id))



  # Make sure we have access to a log entry
  def check_log_entry_access(self, log_id):

    # Make sure we are actually logged in
    self.check_auth()

    # Check if the ticket belongs to this user
    if TicketLogLogic(log_id).check_consumer_access(sess.user_id) is False:
      self.raise_badrequest("Log entry %s is not readable by user %s" % (log_id,sess.user_id))

  # Check ticket area for being allowed
  def check_file_area(self, area):
    if area not in ("input","result"):
      self.raise_badrequest("Invalid file area %s requested" % area)



class TicketsAPI (TicketsAPIBase):

  # List all the tickets (tickets)
  def GET(self):
    
    # The user must be logged in
    self.check_auth()

    # Select from the database
    user_id = sess.user_id
    qresult = db.query(
        ("select T.id, S.name as service, T.status from tickets T, services S "
         "where T.service_githash = S.githash and T.user_id = $user_id and T.status != 'deleted' "
         "order by T.id"),
        vars=locals());

    return query_as_reqfmt(qresult, ['id','service','status'])

  def POST(self):

    # The user must be logged in
    self.check_auth()

    # Get the requested service ID
    githash = self.get_service_githash()

    # Make sure the service exists
    res_svc = db.select("services",where="githash=$githash",vars=locals())
    if len(res_svc) != 1:
      self.raise_badrequest("Service %s is not available" % service_name)

    # Make sure that the user is allowed to create more tickets
    user_id = sess.user_id;
    n_tickets = db.query("select count(id) from tickets where user_id=$user_id and status <> 'deleted'", 
                         vars=locals())[0].count;
    n_allowed = db.query("select max_tickets from users U, user_tiers T where U.id = $user_id and U.tier = T.tier",
                         vars=locals())[0].max_tickets;
    if(n_tickets >= n_allowed):
      self.raise_badrequest("Maximum allowed number of open tickets (%d) exceeded." % n_allowed)

    # Create a new ticket
    ticket_id = db.insert("tickets",user_id=sess.user_id,service_githash=githash,status="init")

    # Also add an entry into the history
    db.insert("ticket_history", ticket_id = ticket_id, status = "init")

    # Empty the directory for this ticket (in case it exists from a previous DB)
    for area in ('input','results'):
      TicketLogic(ticket_id).erase_dir(area)

    return ticket_id


class TicketFilesAPI (TicketsAPIBase):

  def GET(self, ticket_id, area):

    # Make sure we have access to this ticket
    self.check_ticket_access(ticket_id)

    # Send the directory contents as CSV
    csv = TicketLogic(ticket_id).list_files(area)
    web.header('Content-Type','text/csv')
    return csv

  def POST(self, ticket_id, area):

    # Make sure we have access to this ticket
    self.check_ticket_access(ticket_id, ['init'])

    # Data directory
    x = web.input(myfile={})
    try:
      TicketLogic(ticket_id).receive_file(area, x.myfile)
      return "success"

    except:
      raise web.badrequest()


class TicketFileDownloadAPI (TicketsAPIBase):

  # Download the file
  def GET(self, ticket_id, area, file_index):

    # To download files, we must have claimed this ticket
    self.check_ticket_access(ticket_id)

    # Serve up the requested file
    filename = TicketLogic(ticket_id).get_nth_file(area, file_index)
    web.header("Content-Disposition", "attachment; filename=\"%s\"" % os.path.basename(filename))
    web.header("Content-Type", "application/octet-stream")
    web.header("Content-Length", os.path.getsize(filename))
    web.header("Content-transfer-encoding","binary")
    return open(filename, "rb").read()


class TicketStatusAPI (TicketsAPIBase):

  def GET(self, ticket_id):

    # Make sure we have access to this ticket
    self.check_ticket_access(ticket_id)

    # Return the status of this ticket 
    return db.select("tickets", where="id=$ticket_id", vars=locals())[0].status;

  def POST(self, ticket_id):

    # New status must be supplied
    new_status = web.input().status

    # Make sure we have the ticket 
    self.check_ticket_access(ticket_id, ["init"])

    # Check if the current status is appropriate for the new status
    if new_status == "ready":
      with db.transaction():
        tl = TicketLogic(ticket_id)
        rtn_status = tl.set_status(new_status)
        tl.append_log("info", "Ticket received and queued for processing")
        return rtn_status

    self.raise_badrequest("Changing ticket status to %s is not supported" % new_status)


class TicketLogAPI (TicketsAPIBase):

  def GET(self, ticket_id):

    # Make sure we have access to this ticket
    self.check_ticket_access(ticket_id)

    # Did the user specify a starting date
    start_id=0
    if "since" in web.input():
      start_id=web.input().since

    # Get all the log entries since the last one
    qresult = TicketLogic(ticket_id).get_logs(start_id)

    # Return the log entries
    return query_as_reqfmt(qresult, ['id','atime','category','attachments','message'])


class TicketLogAttachmentAPI (TicketsAPIBase):

  def GET(self, log_id):

    # Make sure we have access to this log entry
    self.check_log_entry_access(log_id)

    # Get the list of all attachments with URLs
    qresult = TicketLogLogic(log_id).get_attachments()

    # Return as CSV
    return query_as_reqfmt(qresult, ['id','description','mime_type','url'])


class TicketProgressAPI (TicketsAPIBase):

  def GET(self, ticket_id):

    # Make sure we have access to this ticket
    self.check_ticket_access(ticket_id)

    # Return progres as a string
    return TicketLogic(ticket_id).total_progress()
      

class TicketQueuePositionAPI (TicketsAPIBase):

  def GET(self, ticket_id):

    # Make sure we have access to this ticket
    self.check_ticket_access(ticket_id)

    # Return progres as a string
    return TicketLogic(ticket_id).queue_position()
    

# Return complete detail of a ticket in JSON
class TicketDetailAPI (TicketsAPIBase):

  def GET(self, ticket_id):

    # Make sure we have access to this ticket
    self.check_ticket_access(ticket_id)

    # Initialize the query result
    qr = TicketLogic(ticket_id).get_detail()

    # Return the JSON for this data
    web.header('Content-Type','application/json')
    return json.dumps({"result" : qr}, default=my_json_converter)

# Delete a ticket
class TicketDeleteAPI(TicketsAPIBase):

  def GET(self, ticket_id):

    self.check_ticket_access(ticket_id)
    return TicketLogic(ticket_id).delete_ticket()

class TicketRetryAPI(TicketsAPIBase):

  def GET(self, ticket_id):

    # Check that the status of the ticket is correct
    self.check_ticket_access(ticket_id, ["failed","timeout"])

    # TODO: check that the number of retries has not been exceeded
    return TicketLogic(ticket_id).retry()


# Base API for ticket provider classes    
class ProviderAPIBase(AbstractAPI):

  # Make sure that the user has access to the named service
  def check_service_access_by_githash(self, service_githash):

    # Make sure we are actually logged in
    self.check_auth()

    # Check if the user has access to this service's tickets
    if ServiceLogic(service_githash).check_provider_access(sess.user_id) is False:
      self.raise_unauthorized("You are not a provider for service %s " % service_githash)
    
  # Check if the provider has access to a given ticket
  def check_ticket_access(self, ticket_id, status_list = None):

    # Make sure we are actually logged in
    self.check_auth()

    # Check if the ticket belongs to this user
    if TicketLogic(ticket_id).check_provider_access(sess.user_id, status_list) is False:
      self.raise_badrequest("Ticket %s not found for user %s" % (ticket_id,sess.user_id))

  # Check if the provider has claimed the ticket
  def check_ticket_claimed(self, ticket_id):

    # Make sure we are actually logged in
    self.check_auth()

    # Check if the ticket belongs to this user
    if TicketLogic(ticket_id).check_provider_claimed(sess.user_id) is False:
      self.raise_badrequest("Ticket %s has not been claimed by user %s" % (ticket_id,sess.user_id))

    # Check that the ticket has not been deleted
    if TicketLogic(ticket_id).is_not_deleted() is False:
      self.raise_badrequest("Ticket %s has been deleted " % ticket_id)

  # Check if the provider can edit a log entry
  def check_log_entry_access(self, log_id):

    # Make sure we are actually logged in
    self.check_auth()

    # Check if the ticket belongs to this user
    if TicketLogLogic(log_id).check_provider_access(sess.user_id, ('open')) is False:
      self.raise_badrequest("Log entry %s is not writable by user %s" % (log_id,sess.user_id))

  # Get the provider name and code from web input
  def get_provider_info(self):

    # Get the provider name
    provider_name = web.input().provider

    # Get the optional provider code
    provider_code = "default"
    if 'code' in web.input():
      provider_code = web.input().code

    return (provider_name, provider_code)





class ProviderServicesAPI (ProviderAPIBase):

  # List all the tickets (tickets)
  def GET(self):
    
    # The user must be logged in
    self.check_auth()

    # Just list all the services that the provider has access to
    user_id = sess.user_id
    qresult = db.query(
        "select S.name,S.version,S.githash,PA.provider "
        "from services S, provider_access PA, provider_services PS "
        "where S.githash = PS.service_githash and PA.provider = PS.provider_name "
        "  and PA.user_id = $user_id",
        vars=locals());

    return query_as_reqfmt(qresult, ['name','version','githash','provider'])


class ProviderServiceTicketsAPI (ProviderAPIBase):

  # List all the tickets (tickets)
  def GET(self, service_name):
    
    # The user must have access to the service name
    self.check_service_access_by_githash(service_name)

    # List all of the tickets that are available under this service
    user_id = sess.user_id
    qresult = db.query(
        "select T.* from tickets T, services S "
        "where T.service_id = S.id and S.name = $service_name",
        vars=locals());

    return query_as_reqfmt(qresult, ['id','status'])

class ProviderServiceTicketsAPI (ProviderAPIBase):

  # List all the tickets (tickets)
  def GET(self, service_name):
    
    # The user must have access to the service name
    self.check_service_access_by_githash(service_name)

    # List all of the tickets that are available under this service
    user_id = sess.user_id
    qresult = db.query(
        "select T.* from tickets T, services S "
        "where T.service_id = S.id and S.name = $service_name",
        vars=locals());

    return query_as_reqfmt(qresult, ['id','status'])


class ProviderServiceClaimsAPI (ProviderAPIBase):

  # List all the claimed tickets for this service
  def GET(self, service_githash):

    # The user must have access to the service name
    self.check_service_access_by_githash(service_name)

    # List all of the tickets that are under this service and claimed by this provider
    user_id = sess.user_id
    qresult = db.query(
        "select C.*, S.name as service_name from claim_history C, tickets T, services S "
        "where T.service_id = S.id and C.ticket_id = T.id"
        "  and S.name = $service_name"
        "  and T.status = 'claimed'"
        "  and C.provider_id = $user_id",
        vars=locals());

    return query_as_reqfmt(qresult, ['ticket_id','service_name','provider_code','atime'])

  # Claim the highest priority ticket under this service
  def POST(self, service_githash):

    # The user must have access to the service name
    self.check_service_access_by_githash(service_githash)

    # Get the provider info
    (provider_name, provider_code) = self.get_provider_info()

    # Try to claim the ticket
    ticket_id = ServiceLogic(service_githash).claim_ticket(sess.user_id, provider_name, provider_code)

    # If there is no ticket to claim, we return 0, this is more meaningful than
    # a bad request header
    if ticket_id is None:
      return -1;

    # Return the claimed ticket ID
    return ticket_id

class ProviderMultipleServiceClaimsAPI (ProviderAPIBase):

  # The caller passes in a comma-separated list of services. The server returns the 
  # ticket ID, service name and service git-hash that was selected for servicing
  def POST(self):

    if "services" not in web.input():
      self.raise_badrequest("Missing 'services' parameter")

    # Split services on the comma and add to query string
    svclist = web.input().services.split(',')
    for svc in svclist:
      self.check_service_access_by_githash(svc)

    # Get the provider info
    (provider_name, provider_code) = self.get_provider_info()

    # Call the business logic method
    qresult = ClaimLogic(sess.user_id, provider_name, provider_code).claim_multiservice(svclist)
    if qresult is not None:
      return query_as_reqfmt(qresult, ['id', 'service_githash', 'status'])


class ProviderTicketStatusAPI (ProviderAPIBase):

  # Provide the status of this ticket
  def GET(self, ticket_id):
    
    # The user must be logged in and have access to this ticket
    self.check_ticket_access(ticket_id)

    # Return the status of this ticket 
    return db.select("tickets", where="id=$ticket_id", vars=locals())[0].status;

  # Set the status of the ticket
  def POST(self, ticket_id):

    # Make sure we have access to this ticket
    self.check_ticket_claimed(ticket_id)

    # Get the new desired status
    new_status = web.input().status

    # Check if the current status is appropriate for the new status
    if new_status not in ["failed", "success"]:
      self.raise_badrequest("Cannot set status of ticket to %s" % new_status)

    # Set the status of the ticket in the database
    return TicketLogic(ticket_id).set_status(new_status)



class ProviderTicketFilesAPI (ProviderAPIBase):

  # List all of the files associated with this ticket
  def GET(self, ticket_id, area):
    
    # In order to list files, we must have claimed this ticket
    self.check_ticket_claimed(ticket_id)

    # Return listing as CSV
    csv = TicketLogic(ticket_id).list_files(area)
    web.header('Content-Type','text/csv')
    return csv

  def POST(self, ticket_id, area):

    # Make sure we have access to this ticket
    self.check_ticket_claimed(ticket_id)

    # Get the form parameters and store file
    x = web.input(myfile={})
    try:
      TicketLogic(ticket_id).receive_file(area, x.myfile)
      return "success"

    except:
      raise web.badrequest()


class ProviderTicketFileDownloadAPI (ProviderAPIBase):

  # Download the file
  def GET(self, ticket_id, area, file_index):

    # To download files, we must have claimed this ticket
    self.check_ticket_claimed(ticket_id)

    # Serve up the requested file
    filename = TicketLogic(ticket_id).get_nth_file(area, file_index)
    web.header("Content-Disposition", "attachment; filename=\"%s\"" % os.path.basename(filename))
    web.header("Content-Type", "application/octet-stream")
    web.header("Content-transfer-encoding","binary")
    return open(filename, "rb").read()


# Creates a log message. All the 'free' attachments associated with the ticket 
# will be associated with the current log message
class ProviderTicketLogAPI (ProviderAPIBase):

  # Add an error or warning message
  def POST(self, ticket_id, category):

    # To post to the log, we must have claimed this ticket
    self.check_ticket_claimed(ticket_id)

    # Add log entry and get log id
    return TicketLogic(ticket_id).append_log(category, web.input().message)


# This class handles associating attachments with ticket.
class ProviderTicketAttachmentAPI (ProviderAPIBase):

  # Upload an attachment for a ticket
  def POST(self, ticket_id):

    # To post to the log, we must have claimed this ticket
    self.check_ticket_claimed(ticket_id)

    # Get the description
    if "desc" not in web.input():
      self.raise_badrequest("Missing attachment description for log entry %d", log_id)

    # Mime type is optional
    mime_type = None
    if "mime_type" in web.input():
      mime_type = web.input().mime_type

    # Read the input
    x = web.input(myfile={})
    
    # Create an entry for the attachment in the database
    filepath=x.myfile.filename.replace('\\','/') 
    filename=filepath.split('/')[-1] 
    tlogic = TicketLogic(ticket_id)
    (aid, ahash, afile) = tlogic.add_attachment(web.input().desc, filename, mime_type)

    # Store the attachment
    fout = open(afile,'w') # creates the file where the uploaded file should be stored
    fout.write(x.myfile.file.read()) # writes the uploaded file to the newly created file.
    fout.close() # closes the file, upload complete.

    # Return the aid
    return aid


class ProviderTicketProgressAPI (ProviderAPIBase):

  # Get the progress for a particular chunk
  def GET(self, ticket_id):

    # To post progress, we must have claimed this ticket
    self.check_ticket_claimed(ticket_id)

    # Return the progress value
    return TicketLogic(ticket_id).total_progress()


  # Set the progress for a particular chunk
  def POST(self, ticket_id):

    # To post progress, we must have claimed this ticket
    self.check_ticket_claimed(ticket_id)

    # Write the progress 
    TicketLogic(ticket_id).set_chunk_progress(
      web.input().chunk_start, web.input().chunk_end, web.input().progress)

    return "success";


# This API is for downloading blobs directly by a UUID code - clickable and shareable
# links. There is no authentication involved
class DirectDownloadAPI (AbstractAPI):

  # There is only a GET method
  def GET(self, hashstr):

    # Find the blob in log attachments
    pattern = hashstr + '%'
    res = db.select("ticket_attachment", where="uuid like $pattern", vars=locals());

    # Did we find a blob?
    if len(res) == 0:
      self.raise_badrequest("Resource %s not found" % hashstr)

    # Get the dict for the first row
    row = res[0]

    # The directory of the file
    filedir = 'datastore/attachments/%08d' % int(row.ticket_id)

    # Find the file in the directory
    for file in os.listdir(filedir):
      if file.startswith(row.uuid):
        web.header("Content-Type", row.mime_type)
        return open(filedir + '/' + file,"rb").read() # Notice 'rb' for reading images

    self.raise_badrequest("Resource %s not found in directory" % hashstr)

     
class AdminAbstractAPI(AbstractAPI):

  # Check authorization at administrator level
  def check_auth(self):
    super(AdminAbstractAPI,self).check_auth()
    email = sess.email
    res = db.select('users', where="email=$email", vars=locals())
    if res[0].sysadmin is not True:
      self.raise_unauthorized("Insufficient privileges")


class AdminProvidersAPI(AdminAbstractAPI):

  def GET(self):
    self.check_auth()

    # Generate list of available providers
    res = db.select('providers');
    return query_as_reqfmt(res, ['name'])

  def POST(self):
    self.check_auth()

    # Create a new provider
    pname = web.input().name

    # If the provider does not exist, add them, otherwise mark them as current
    db.query(
      "insert into providers values($pname, true) "
      "    on conflict (name) do update set current=true;", vars=locals());

    # Return if successful
    return "success"
    

class AdminProviderDeleteAPI(AdminAbstractAPI):

  def GET(self, provider):
    self.check_auth()

    # Make the provider inactive
    db.update("providers", where="name=$provider", current=False, vars=locals())

    # Detach provider from all its services
    db.update("provider_services", where="provider_name=$provider", current=False, vars=locals())
    
    # Clear the orphaned services
    ProviderServiceLogic().clean_orphaned_services()


class AdminProviderUsersAPI(AdminAbstractAPI):

  def GET(self,provider):
    self.check_auth()
    res = db.query(
        "select U.id, U.email,P.admin from users U, provider_access P "
        "where U.id = P.user_id and P.provider = $provider", vars=locals())
    return query_as_reqfmt(res, ['id', 'email','admin'])

  def POST(self,provider):
    self.check_auth()
    email = web.input().email
    isadmin = None
    if 'admin' in web.input():
      isadmin=int(web.input().admin)

    res = db.select('users', where="email=$email", vars=locals())
    if len(res) != 1:
      self.raise_unauthorized('Email unrecognized by the system')
    user_id = res[0].id

    with db.transaction():
      db.delete('provider_access', where='user_id=$user_id and provider=$provider', vars=locals())
      db.insert('provider_access', user_id=user_id, provider=provider, admin=bool(isadmin))

    return 'Added user %s to provider %s' % (email, provider)

class AdminProviderUsersDeleteAPI(AdminAbstractAPI):

  def GET(self,provider,user_id):
    self.check_auth()
    with db.transaction():
      db.delete('provider_access', where='user_id=$user_id and provider=$provider', vars=locals())


class AdminProviderServicesAPI(AdminAbstractAPI):

  # List all provider services
  def GET(self, provider):
    self.check_auth()
    res = db.query(
      "select * from services S, provider_services P "
      "where S.githash = P.service_githash and P.provider_name = $provider "
      "order by S.name, S.version", vars=locals())
    return query_as_reqfmt(res, ['name','version','githash','shortdesc'])

  # Add a service for a provider
  def POST(self, provider):
    self.check_auth()

    # The repo must be supplied
    repo_url = web.input().repo

    # The reference can be a githash or a branch or a tag
    ref_spec = web.input().ref

    # Create temporary directory to check out repo
    d_temp = tempfile.mkdtemp()
    os.environ['GIT_TERMINAL_PROMPT'] = '0'

    try:
      # Fetch the remote repository
      repo = Repo.clone_from(repo_url, d_temp)
      repo.remotes.origin.fetch(ref_spec)
      repo.git.checkout('FETCH_HEAD')

      # Get the GitHash of the checkin
      githash = repo.head.object.hexsha

      # Read the json service descriptor
      f_json = open(os.path.join(repo.working_dir,'service.json'))
      j = json.load(f_json)
      f_json.close()

    except:
      print(traceback.format_exc())
      self.raise_badrequest("Error fetching Git repository")

    # Check if the service clashes with an existing service. In that case
    # we reject this update
    q_clash=db.query(
      "select count(githash) from services "
      "where name=$j['name'] and version=$j['version'] and current=TRUE "
      "      and githash <> $githash ", vars=locals())

    if q_clash[0].count > 0:
      self.raise_badrequest("A service with same name and version already exists")

    # Perform checkin of the new repo
    with db.transaction():

      # Insert the actual service. If the service exists, mark it as current. We assume
      # that the attributes of a service stay fixed if the githash has not changed, which
      # is the basic assumption with using git!
      jdump = json.dumps(j)
      db.query(
        "insert into services "
        "    values ($j['name'], $githash, $j['version'], left($j['shortdesc'],78), $jdump) "
        "    on conflict (githash) do update set current = true ", vars = locals());

      # Assign the service to the provider
      db.query(
        "insert into provider_services values($provider, $githash) "
        "    on conflict (provider_name, service_githash) "
        "    do update set current = true", vars=locals())

    # Create a copy of the repo in the datastore directory
    saved_dir = 'datastore/services/%s' % githash
    if not os.path.exists(saved_dir):
      os.makedirs(saved_dir)
      repo.clone(os.path.abspath(saved_dir))

    # Finally, return the githash
    return githash
    
    
class AdminProviderServicesDeleteAPI(AdminAbstractAPI):

  def GET(self, provider, githash):
    self.check_auth()

    # Clear the current flag in the provider_service relation (provider no longer offers service)
    db.update("provider_services", 
              where="service_githash=$githash and provider_name=$provider",
              current=False, vars=locals())

    # If there are any orphaned services as the result of this, remove them
    ProviderServiceLogic().clean_orphaned_services()

    # Success
    return "success"


class AdminTicketsAPI(AdminAbstractAPI):

  # Get all the tickets with status
  def GET(self):

    self.check_auth();

    # Select from the database
    qresult = db.query(
      "select T.id, T.status, U.email, "
      "       case when S.name is null then T.service_githash else S.name end as service, "
      "       round(extract(epoch from max(TH.atime) - min(TH.atime)) / 60) as duration  "
      "from tickets T "
      "       left join services S on T.service_githash = S.githash "
      "       left join users U on T.user_id = U.id "
      "       left join ticket_history TH on T.id = TH.ticket_id "
      "where T.status != 'deleted' "
      "group by T.id, T.status, U.email, service "
      "order by T.id");

    return query_as_reqfmt(qresult, ['id','email','service','status','duration'])


class AdminPurgeTicketsAPI(AdminAbstractAPI):

  def POST(self, ticket_mode):

    self.check_auth();

    # Check the number of days to purge
    if 'days' in web.input():
      interval="%f days" % float(web.input().days)
    elif 'hours' in web.input():
      interval="%f hours" % float(web.input().hours)
    else:
      interval="7 days"

    # What kinds of tickets to purge (completed or all)
    if ticket_mode == 'completed':
      status_list="('failed','success','timeout')"
    else:
      status_list="('failed','success','timeout','init','ready','claimed')"

    # List the tickets that can be purged
    qresult = db.query(
      "select T.id,H.atime,T.status from tickets T, ticket_history H "
      "where T.id = H.ticket_id and T.status in %s "
      "  and H.status = 'init' and now() - H.atime > interval $interval" % status_list,
      vars=locals());

    # Purge each of the tickets in the list
    for row in qresult:
      TicketLogic(row.id).delete_ticket()

    # Get the list of tickets 
    return "Purged %d tickets" % len(qresult)



# Argument parser
parser = argparse.ArgumentParser()
parser.add_argument("--server", help="Run as a stand-alone server", action="store_true")
parser.add_argument("--port", help="Port on which to run stand-alone server", type=int, default=8080)
pargs = parser.parse_args();

# Which action to take
if pargs.server:
  sys.argv = [str(pargs.port)]
  app.run()
else:
  application=app.wsgifunc()
###  if __name__ == '__main__' :
###  app.run()
