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
from pprint import pprint
from os import walk
from os.path import basename
from oauth2client import client
from apiclient.discovery import build
from git import Repo

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
  r"/about", "AboutPage",
  r"/api/login", "LoginAPI",
  r"/api/oauth2cb", "OAuthCallbackAPI",
  r"/api/services", "ServicesAPI",
  r"/api/services/([a-f0-9]+)/detail", "ServicesDetailAPI",
  r"/api/tickets", "TicketsAPI",
  r"/api/tickets/(\d+)/files/(input|results)", "TicketFilesAPI",
  r"/api/tickets/(\d+)/files/(input|results)/(\d+)", "TicketFileDownloadAPI",
  r"/api/tickets/(\d+)/status", "TicketStatusAPI",
  r"/api/tickets/(\d+)/log", "TicketLogAPI",
  r"/api/tickets/(\d+)/progress", "TicketProgressAPI",
  r"/api/tickets/(\d+)/queuepos", "TicketQueuePositionAPI",
  r"/api/tickets/(\d+)/detail", "TicketDetailAPI",
  r"/api/tickets/(\d+)/delete", "TicketDeleteAPI",
  r"/api/tickets/logs/(\d+)/attachments", "TicketLogAttachmentAPI",
  r"/api/pro/services", "ProviderServicesAPI",
  r"/api/pro/services/([\w\-]+)/tickets", "ProviderServiceTicketsAPI",
  r"/api/pro/services/([a-f0-9]+)/claims", "ProviderServiceClaimsAPI",
  r"/api/pro/tickets/(\d+)/files/(input|results)", "ProviderTicketFilesAPI",
  r"/api/pro/tickets/(\d+)/files/(input|results)/(\d+)", "ProviderTicketFileDownloadAPI",
  r"/api/pro/tickets/(\d+)/status", "ProviderTicketStatusAPI",
  r"/api/pro/tickets/(\d+)/(error|warning|info|log)", "ProviderTicketLogAPI",
  r"/api/pro/tickets/(\d+)/attachments", "ProviderTicketAttachmentAPI",
  r"/api/pro/tickets/(\d+)/progress", "ProviderTicketProgressAPI",
  r"/api/admin/catalog","AdminCatalogAPI", 
  r"/api/admin/catalog/rebuild","AdminCatalogRebuildAPI", 
  r"/api/admin/providers/([\w\-]+)/users","AdminProviderUsersAPI", 
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

# Create the session object with database storate
sess = web.session.Session(
    app, web.session.DBStore(db, 'sessions'), 
    initializer={'loggedin': False, 'acceptterms': False})

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
  print "wow"
  text = getattr(render, page)(*args);
  print text
  return render.style(md.convert(unicode(text)));

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
        scope='https://www.googleapis.com/auth/userinfo.email',
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

# Home Page handler
class index:
  def GET(self):

    # Create the URL for authorization
    auth_url=None
    if sess.loggedin == False:
      auth_url = OAuthHelper().auth_url()

    # The redirect URL for after authentication
    sess.return_uri=web.ctx.home
    return render_markdown("hohum", False, None, auth_url)

# Handler for accepting terms of service
class AcceptTermsRequest:
  def POST(self):
    cb=web.input().cb
    if cb == 'on':
      sess.acceptterms = True
      raise web.redirect("/token")
    else:
      sess.acceptterms = False
      raise web.redirect("/logout")

# Token request handler
class TokenRequest:

  def GET(self):

    # Create the URL for authorization
    auth_url=None
    token=None
    if sess.loggedin == False:
      auth_url = OAuthHelper().auth_url()
    else:
      email = sess.email
      res = db.select('users', where="email=$email", vars=locals())
      token=res[0].passwd

    # Get the user to accept the terms of service
    sess.return_uri=web.ctx.home + "/token"
    return render_markdown("token", auth_url, token)


class LogoutPage:

  def GET(self):
    sess.kill()
    raise web.seeother('/')

class ServicesPage:

  def GET(self):
    
    if sess.loggedin is not True:
      raise web.redirect("/")

    services=db.select("services")
    return render_markdown("services_home", services)

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
      "select T.id, T.status from tickets T, providers P "
      "where T.service_id = P.service_id and P.user_id = $provider_id "
      "  and T.id = $self.ticket_id",
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
      "select sum((chunk_end-chunk_start) * progress) as x from ticket_progress "
      "where ticket_id=$self.ticket_id", 
      vars=locals())
    if len(res) > 0:
      return res[0].x
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
    db.update("tickets", where="id = $self.ticket_id", status = 'deleted', vars=locals())
    new_status = db.select("tickets", where="id=$self.ticket_id", vars=locals())[0].status;

    # Empty the directory for this ticket (in case it exists from a previous DB)
    for area in ('input','results'):
      TicketLogic(self.ticket_id).erase_dir(area)

    # Clear the attachments
    TicketLogic(self.ticket_id).erase_attachments()

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


# Logic around the service/provider catalog
class CatalogLogic:
  
  def rebuild(self):

    # Scan the catalog directory for all providers
    rcat = Repo('catalog')
    if rcat.bare is True:
      raise web.badrequest()

    # Clear the database of provider and service tables
    db.delete('provider_services', where='service_githash is not null')
    db.delete('services', where='name is not null')
    db.delete('providers', where='name is not null')

    for pro in rcat.submodules:
      if pro.name.startswith('providers/'):

        # Get the name of the provider
        pname = os.path.basename(pro.name)

        # Add the provider to the database
        db.insert('providers', name=pname)

        # Run over all the available services
        for q in pro.children():
          try:
            f_json = open(os.path.join(q.abspath,'service.json'))
            j = json.load(f_json)
            f_json.close()

            with db.transaction():

              # Insert the actual service
              db.insert('services',
                        name = j['name'], 
                        githash = q.hexsha,
                        version = j['version'], 
                        shortdesc = j['shortdesc'],
                        json = json.dumps(j))

              # Assign the service to the provider
              db.insert('provider_services',
                        provider_name = pname,
                        service_githash = q.hexsha)
          except:
            print("Unexpected error:", sys.exc_info())
        

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
      db.update("tickets", where="id = $ticket_id", status = "claimed", vars=locals())

      # Update the log for the user
      TicketLogic(ticket_id).append_log("info",
          "Ticket claimed by provider %s instance %s" % (provider_name,provider_code));

      # Return the ticket ID
      return ticket_id


# =====================
# RESTful API
# =====================

def my_json_converter(o):
    if isinstance(o, datetime.datetime):
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
    if sess.loggedin is False:
      self.raise_unauthorized("You are not logged in!")

  # Raise an unauthorized error with a message
  def raise_unauthorized(self, message = "unauthorized"):
    raise web.HTTPError("401 unauthorized", {}, message)

  # Raise an unauthorized error with a message
  def raise_badrequest(self, message = "bad request"):
    raise web.HTTPError("400 bad request", {}, message)

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
      alfabis_id=res[0].id
    else:
      passwd=os.urandom(24).encode('hex')
      db.insert('users', email=email, passwd=passwd, dispname=user_info.get("name"))

    # Set the user information in the session
    sess.email = user_info.get('email')
    sess.name = user_info.get('name')
    sess.user_id = alfabis_id
    sess.loggedin = True

    # Redirect to the home page
    raise web.redirect(sess.return_uri)
    

class LoginAPI:

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

      # Now that the user has used the token, generate a new token (so that there
      # is no security risk from sharing tokens)
      new_token=os.urandom(24).encode('hex')
      db.update("users", where="passwd=$token", passwd = new_token, vars=locals())

      return ("logged in as %s \n" % sess.email);

    else:
      sess.kill();
      raise web.unauthorized()

    #except:
    #  raise web.badrequest()

class ServicesAPI (AbstractAPI):

  def GET(self):
    
    self.check_auth()

    qresult = db.select("services");
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


class TicketsAPIBase(AbstractAPI):

  # Make sure that the user has access to this particular
  # ticket. This also makes sure that the used is logged in
  def check_ticket_access(self, ticket_id, status_list = None):
    
    # Make sure we are actually logged in
    self.check_auth()

    # Check if the ticket belongs to this user
    if TicketLogic(ticket_id).check_consumer_access(sess.user_id, status_list) is False:
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
    githash = web.input().githash

    # Create a new ticket
    res_svc = db.select("services",where="githash=$githash",vars=locals())
    if len(res_svc) != 1:
      self.raise_badrequest("Service %s is not available" % service_name)
    ticket_id = db.insert("tickets",user_id=sess.user_id,service_githash=githash,status="init")

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

    # Check if the current status is appropriate for the new status
    if new_status == "ready":
      with db.transaction():
        self.check_ticket_access(ticket_id, ["init"])
        n = db.update("tickets", where="id = $ticket_id", status = new_status, vars=locals())
        return db.select("tickets", where="id=$ticket_id", vars=locals())[0].status;

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
    qr = {}

    # Get the status of this ticket
    qr['status'] = db.select('tickets', where='id=$ticket_id', vars=locals())[0].status;

    # Depending on status, assign progress
    if qr['status'] == 'claimed':
      qr['progress'] = float(TicketLogic(ticket_id).total_progress())
    elif qr['status'] in ('failed','success','timeout'):
      qr['progress'] = 1.0
    else:
      qr['progress'] = 0.0

    # User can request partial update since given log_id
    start_id=0
    if "since" in web.input():
      start_id=web.input().since

    # Get the logs for this ticket
    qresult = TicketLogic(ticket_id).get_logs(start_id)

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

    # Return the JSON for this data
    web.header('Content-Type','application/json')
    return json.dumps({"result" : qr}, default=my_json_converter)

# Delete a ticket
class TicketDeleteAPI(TicketsAPIBase):

  def GET(self, ticket_id):

    self.check_ticket_access(ticket_id)
    return TicketLogic(ticket_id).delete_ticket()

# Base API for ticket provider classes    
class ProviderAPIBase(AbstractAPI):

  # Make sure that the user has access to the named service
  def check_service_access_by_githash(self, service_githash):

    # Make sure we are actually logged in
    self.check_auth()

    # Check if the user has access to this service's tickets
    if ServiceLogic(service_githash).check_provider_access(sess.user_id) is False:
      self.raise_unauthorized("You are not a provider for service %s " % service_name)
    
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

    # Get the provider name
    provider_name = web.input().provider

    # Get the optional provider code
    provider_code = "default"
    if 'code' in web.input():
      provider_code = web.input().code

    # Try to claim the ticket
    ticket_id = ServiceLogic(service_githash).claim_ticket(sess.user_id, provider_name, provider_code)

    # If there is no ticket to claim, we return 0, this is more meaningful than
    # a bad request header
    if ticket_id is None:
      return -1;

    # Return the claimed ticket ID
    return ticket_id


 
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
    db.update("tickets", where="id = $ticket_id", status = new_status, vars=locals())

    # All good!
    return db.select("tickets", where="id=$ticket_id", vars=locals())[0].status;



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


class AdminCatalogAPI(AdminAbstractAPI):

  def GET(self):
    self.check_auth()
    return "You are the admin, indeed\n"

  
class AdminCatalogRebuildAPI(AdminAbstractAPI):

  def GET(self):
    self.check_auth()
    cl = CatalogLogic()
    cl.rebuild()
    return "Rebuilt service catalog"

class AdminProviderUsersAPI(AdminAbstractAPI):

  def GET(self,provider):
    self.check_auth()
    res = db.query(
        "select U.email,P.admin from users U, provider_access P "
        "where U.id = P.user_id and P.provider = $provider", vars=locals())
    return query_as_reqfmt(res, ['email','admin'])

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

###  if __name__ == '__main__' :
###  app.run()
application=app.wsgifunc()
