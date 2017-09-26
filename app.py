#!/usr/bin/python
import web,sys
import markdown
import json
import os
import hashlib
import csv
import StringIO
import glob
import uuid
import mimetypes
from pprint import pprint;
from os import walk;
from os.path import basename;

# Needed for session support
web.config.debug = False

# URL mapping
urls = (
  r'/', 'index',
  r"/login", "LoginPage",
  r"/register", "RegisterPage",
  r"/logout", "LogoutPage",
  r"/api/login", "LoginAPI",
  r"/api/services", "ServicesAPI",
  r"/api/tickets", "TicketsAPI",
  r"/api/tickets/(\d+)/files", "TicketFilesAPI",
  r"/api/tickets/(\d+)/status", "TicketStatusAPI",
  r"/api/tickets/(\d+)/log", "TicketLogAPI",
  r"/api/tickets/(\d+)/progress", "TicketProgressAPI",
  r"/api/tickets/(\d+)/queuepos", "TicketQueuePositionAPI",
  r"/api/tickets/logs/(\d+)/attachments", "TicketLogAttachmentAPI",
  r"/api/pro/services", "ProviderServicesAPI",
  r"/api/pro/services/([\w\-]+)/tickets", "ProviderServiceTicketsAPI",
  r"/api/pro/services/([\w\-]+)/claims", "ProviderServiceClaimsAPI",
  r"/api/pro/tickets/(\d+)/files", "ProviderTicketFilesAPI",
  r"/api/pro/tickets/(\d+)/files/(\d+)", "ProviderTicketFileDownloadAPI",
  r"/api/pro/tickets/(\d+)/status", "ProviderTicketStatusAPI",
  r"/api/pro/tickets/(\d+)/(error|warning|info|log)", "ProviderTicketLogAPI",
  r"/api/pro/tickets/(\d+)/attachments", "ProviderTicketAttachmentAPI",
  r"/api/pro/tickets/logs/(\d+)/attachments", "ProviderTicketLogAttachmentAPI",
  r"/api/pro/tickets/logs/(\d+)/status", "ProviderTicketLogStatusAPI",
  r"/api/pro/tickets/(\d+)/progress", "ProviderTicketProgressAPI",
  r"/blobs/([a-f0-9]{8})", "DirectDownloadAPI",
  r"/blobs/([a-f0-9]{32})", "DirectDownloadAPI"
  )

# Create the web app
app = web.application(urls, globals())

# Connect to the database
db = web.database(
        host=os.environ['POSTGRES_PORT_5432_TCP_ADDR'],
        port=os.environ['POSTGRES_PORT_5432_TCP_PORT'],
        dbn='postgres', db='alfabis_test', 
        user='postgres', pw='postgres')

# Create the session object with database storate
sess = web.session.Session(
    app, web.session.DBStore(db, 'sessions'), 
    initializer={'loggedin': False})

# Configure the template renderer with session support
render = web.template.render(
    '/home/mac/test/temp/', 
    globals={'markdown': markdown.markdown, 'session': sess}, 
    cache=False);

# Configure the markdown to HTML converter (do we need this really? Why not HTML5?)
md = markdown.Markdown(output_format='html4')

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


# A class that handles authentication. When initialized, it tried to authenticate
# and stores the result of the authentication in its state. It can also be used 
# for more advanced queries about the user
class Authentication:

  def __init__(self, email, passwd):
    self.email,self.passwd = email.strip().lower(),passwd
    passhash = hashlib.sha1("sAlT754-"+passwd).hexdigest()
    try:
      self.ident = db.select('users', where='email=$email', vars=locals())[0]
      if passhash == self.ident['passwd']:
        self.status = 0;                  # successful login
      else:
        self.status = 1;                  # wrong password
    except:
      self.status = 2;                    # unknown user or other issue

  def success(self):
    return (self.status == 0);

  def error_message(self):
    if self.status == 1:
      return "Your email and password do not match"
    elif self.status == 2:
      return "Your email is not in our system"
    else:
      return None

  def user_id(self):
    if self.status == 0:
      return self.ident['id']
    else:
      return None

  def dispname(self):
    if self.status == 0:
      return self.ident['dispname']
    else:
      return None


class index:
  def GET(self):
    return render_markdown("hohum", False, None)

class LoginPage:

  def POST(self):

    # Get the email and password of the user
    email, passwd = web.input().name, web.input().passwd

    # Are we trying to register?
    if "signin" in web.input():

      # Check user against database
      auth = Authentication(email, passwd)
      if auth.success():
        sess.loggedin = True
        sess.email = email
        sess.user_id = auth.user_id()
        sess.dispname = auth.dispname()
        raise web.seeother('/')
      else:
        return render_markdown("hohum", False, auth.error_message())

    else:

      # Redirect to the registration page
      sess.email = email;
      raise web.seeother('/register')

class RegisterPage:

  def GET(self):
    return render_markdown("register", sess.email);

  def POST(self):

    # Get the email and password of the user
    email_raw, fullname, passwd = web.input().email, web.input().fullname, web.input().passwd

    email = email_raw.strip().lower()
    passhash = hashlib.sha1("sAlT754-"+passwd).hexdigest()

    # Insert into the database
    res = db.select('users', where="email=$email", vars=locals())
    if len(res) > 0:
      return render_markdown("register", email, fullname, "This email is already registered")

    db.insert('users', email=email,passwd=passhash,dispname=fullname)
    sess.loggedin = True;
    sess.email = email;
    raise web.seeother('/')


class LogoutPage:

  def GET(self):
    sess.kill()
    raise web.seeother('/')


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

  # Check that the specified provider has actually claimed this ticket 
  def check_provider_claimed(self, provider_id):
    res = db.select("claim_history", 
      where="ticket_id=$self.ticket_id and provider_id=$provider_id",
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

  # Measure the total progress for a ticket
  def total_progress(self):
    res = db.query(
      "select sum((chunk_end-chunk_start) * progress) as x from ticket_progress "
      "where ticket_id=$self.ticket_id", 
      vars=locals())
    if len(res) > 0:
      return res[0].x

  # Measure the total progress for a ticket
  def queue_position(self):
    res = db.query(
      "select count(id) as x from tickets "
      "where service_id = (select service_id from tickets where id = $self.ticket_id) "
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
    filedir = '/home/mac/test/datastore/attachments/%08d' % int(self.ticket_id)
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
    res = db.query(
      "select L.id, L.state from ticket_log L, tickets T, providers P "
      "where T.service_id = P.service_id and P.user_id = $provider_id "
      "  and T.id = L.ticket_id and L.id = $self.log_id",
      vars=locals())
    return len(res) > 0 and (state_list is None or res[0].state in state_list)

  def check_consumer_access(self, user_id):

    res = db.query(
      "select L.id from ticket_log L, tickets T "
      "where T.user_id = $user_id and T.id = L.ticket_id and L.id = $self.log_id",
      vars=locals())

    return len(res) > 0

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
    filedir = '/home/mac/test/datastore/logdata/%08d' % int(self.log_id)
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






# Logic around services. This class is initialized with a service ID
class ServiceLogic:

  def __init__(self, service_name):
    self.service_name = service_name

  def check_provider_access(self, provider_id):
    res = db.query(
      "select * from providers P, services S "
      "where P.service_id = S.id and S.name=$self.service_name "
      "  and user_id = $provider_id",
      vars=locals());
    return len(res) > 0

  def claim_ticket(self, provider_id, provider_code):

    # Create a transaction because this operation must be atomic
    with db.transaction():

      # Get the highest priority 'ready' ticket. TODO: For now the priority is just based
      # on the ticket serial number, but this will need to be updated to use an actual
      # prioritization system in the future
      res = db.query(
          "select T.id from tickets T, services S, providers P "
          "where T.service_id = S.id and P.service_id = S.id "
          "  and P.user_id = $provider_id and S.name = $self.service_name "
          "  and T.status = 'ready' "
          "order by T.id asc limit 1", vars=locals());

      # Nothing returned? Means there are no ready tickets
      if len(res) == 0:
        return None

      # Now we have a ticket
      ticket_id = res[0].id

      # Make an entry in the claims table, to keep track of this claim
      db.insert("claim_history", ticket_id=ticket_id, provider_id=provider_id, provider_code=provider_code)

      # Mark the ticket as claimed
      db.update("tickets", where="id = $ticket_id", status = "claimed", vars=locals())

      # Return the ticket ID
      return ticket_id


# =====================
# RESTful API
# =====================

def query_as_csv(qresult, fields):
  strout = StringIO.StringIO()
  csvout = csv.DictWriter(strout, fieldnames=fields, extrasaction='ignore')
  csvout.writerows(qresult)
  return strout.getvalue()

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


class AbstractAPI:

  # The the file directory for a given ticket
  def get_ticket_filedir(self, ticket_id):
    filedir = '/home/mac/test/datastore/tickets/%08d' % int(ticket_id)
    if not os.path.exists(filedir):
      os.makedirs(filedir)
    return filedir

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

class LoginAPI:

  def POST(self):

    # Get the email and password of the user
    pprint(web.input())
    try:
      email, passwd = web.input().email, web.input().passwd
      auth = Authentication(email, passwd)

      if auth.success():
        sess.loggedin = True
        sess.email = email
        sess.user_id = auth.user_id()
        return "success";

      else:
        sess.kill();
        return "error: %s" % auth.error_message();
    except:
      raise web.badrequest()

class ServicesAPI (AbstractAPI):

  def GET(self):
    
    self.check_auth()

    qresult = db.select("services");
    web.header('Content-Type','text/csv')
    return query_as_csv(qresult, ['name','shortdesc'])


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


class TicketsAPI (TicketsAPIBase):

  # List all the tickets (tickets)
  def GET(self):
    
    # The user must be logged in
    self.check_auth()

    # Select from the database
    user_id = sess.user_id
    qresult = db.query(
        ("select T.id, S.name, T.status from tickets T, services S "
         "where T.service_id = S.id and T.user_id = $user_id "
         "order by T.id"),
        vars=locals());

    web.header('Content-Type','text/csv')
    return query_as_csv(qresult, ['id','name','status'])

  def POST(self):

    # The user must be logged in
    self.check_auth()

    # Get the requested service ID
    service_name = web.input().service

    res_svc = db.select("services",where="name=$service_name",vars=locals())
    if len(res_svc) == 0:
      self.raise_badrequest("Service %s is not available" % service_name)
    service_id = res_svc[0].id
    ticket_id = db.insert("tickets",user_id=sess.user_id,service_id=service_id,status="init")
    return ticket_id


class TicketFilesAPI (TicketsAPIBase):

  def GET(self, ticket_id):

    # Make sure we have access to this ticket
    self.check_ticket_access(ticket_id)
    
    filedir = self.get_ticket_filedir(ticket_id)
    web.header('Content-Type','text/csv')
    return directory_as_csv(filedir)

  def POST(self, ticket_id):

    # Make sure we have access to this ticket
    self.check_ticket_access(ticket_id, ['init'])

    # Data directory
    x = web.input(myfile={})
    print x.keys()
    # if 'file' in x.myfile and 'filename' in x.myfile:
    try:
      filedir = self.get_ticket_filedir(ticket_id)
      filepath=x.myfile.filename.replace('\\','/') # replaces the windows-style slashes with linux ones.
      filename=filepath.split('/')[-1] # splits the and chooses the last part (the filename with extension)

      fout = open(filedir +'/'+ filename,'w') # creates the file where the uploaded file should be stored
      fout.write(x.myfile.file.read()) # writes the uploaded file to the newly created file.
      fout.close() # closes the file, upload complete.
      return "success"

    except:
      raise web.badrequest()


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
    qresult = db.query(
        "select L.*,count(B.attachment_id) as attachments "
        "  from ticket_log L left join ticket_log_attachment B on L.id = B.log_id "
        "  where ticket_id = $ticket_id and id > $start_id group by L.id,log_id",
        vars=locals());

    web.header('Content-Type','text/csv')
    return query_as_csv(qresult, ['id','atime','category','attachments','message'])


class TicketLogAttachmentAPI (TicketsAPIBase):

  def GET(self, log_id):

    # Make sure we have access to this log entry
    self.check_log_entry_access(log_id)

    # Get the list of all attachments with URLs
    urlbase = web.ctx.home + '/blobs/'
    qresult = db.query(
      "select id,description,mime_type,$urlbase || substr(uuid,0,9) as url "
      "  from ticket_attachment A left join ticket_log_attachment B "
      "    on A.id = B.attachment_id "
      "  where B.log_id = $log_id order by id",
      vars=locals());

    # Return as CSV
    web.header('Content-Type','text/csv')
    return query_as_csv(qresult, ['id','description','mime_type','url'])


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
      

# Base API for ticket provider classes    
class ProviderAPIBase(AbstractAPI):

  # Make sure that the user has access to the named service
  def check_service_access_by_name(self, service_name):

    # Make sure we are actually logged in
    self.check_auth()

    # Check if the user has access to this service's tickets
    if ServiceLogic(service_name).check_provider_access(sess.user_id) is False:
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
        "select S.name from providers P, services S "
        "where P.service_id = S.id and user_id = $user_id",
        vars=locals());

    web.header('Content-Type','text/csv')
    return query_as_csv(qresult, ['name'])


class ProviderServiceTicketsAPI (ProviderAPIBase):

  # List all the tickets (tickets)
  def GET(self, service_name):
    
    # The user must have access to the service name
    self.check_service_access_by_name(service_name)

    # List all of the tickets that are available under this service
    user_id = sess.user_id
    qresult = db.query(
        "select T.* from tickets T, services S "
        "where T.service_id = S.id and S.name = $service_name",
        vars=locals());

    web.header('Content-Type','text/csv')
    return query_as_csv(qresult, ['id','status'])

class ProviderServiceTicketsAPI (ProviderAPIBase):

  # List all the tickets (tickets)
  def GET(self, service_name):
    
    # The user must have access to the service name
    self.check_service_access_by_name(service_name)

    # List all of the tickets that are available under this service
    user_id = sess.user_id
    qresult = db.query(
        "select T.* from tickets T, services S "
        "where T.service_id = S.id and S.name = $service_name",
        vars=locals());

    web.header('Content-Type','text/csv')
    return query_as_csv(qresult, ['id','status'])


class ProviderServiceClaimsAPI (ProviderAPIBase):

  # List all the claimed tickets for this service
  def GET(self, service_name):

    # The user must have access to the service name
    self.check_service_access_by_name(service_name)

    # List all of the tickets that are under this service and claimed by this provider
    user_id = sess.user_id
    qresult = db.query(
        "select C.*, S.name as service_name from claim_history C, tickets T, services S "
        "where T.service_id = S.id and C.ticket_id = T.id"
        "  and S.name = $service_name"
        "  and T.status = 'claimed'"
        "  and C.provider_id = $user_id",
        vars=locals());

    web.header('Content-Type','text/csv')
    return query_as_csv(qresult, ['ticket_id','service_name','provider_code','atime'])

  # Claim the highest priority ticket under this service
  def POST(self, service_name):

    # The user must have access to the service name
    self.check_service_access_by_name(service_name)

    # Get the optional provider code
    provider_code = "default"
    if 'code' in web.input():
      provider_code = web.input().code

    # Try to claim the ticket
    ticket_id = ServiceLogic(service_name).claim_ticket(sess.user_id, provider_code)

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
    if new_status not in ["failed"]:
      self.raise_badrequest("Cannot set status of ticket to %s" % new_status)

    # Set the status of the ticket in the database
    db.update("tickets", where="id = $ticket_id", status = new_status, vars=locals())

    # All good!
    return db.select("tickets", where="id=$ticket_id", vars=locals())[0].status;



class ProviderTicketFilesAPI (ProviderAPIBase):

  # List all of the files associated with this ticket
  def GET(self, ticket_id):
    
    # In order to list files, we must have claimed this ticket
    self.check_ticket_claimed(ticket_id)

    # List all of the files
    filedir = self.get_ticket_filedir(ticket_id)

    web.header('Content-Type','text/csv')
    return directory_as_csv(filedir)

class ProviderTicketFileDownloadAPI (ProviderAPIBase):

  # Download the file
  def GET(self, ticket_id, file_index):

    # To download files, we must have claimed this ticket
    self.check_ticket_claimed(ticket_id)

    # Get the ticket directory
    filedir = self.get_ticket_filedir(ticket_id)

    # Get the specified file
    filename = get_indexed_file(filedir, int(file_index))
    if filename is None:
      return self.raise_badrequest("File %s does not exist for ticket %d" % file_index,ticket_id)

    # Serve up the requested file
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


class ProviderTicketLogStatusAPI (ProviderAPIBase):

  # Upload an attachment for the log entry
  def POST(self, log_id):

    # To post to the log, we must have claimed this ticket
    self.check_log_entry_access(log_id)

    # Get the new status
    if "status" not in web.input():
      self.raise_badrequest("Missing status for log entry %d", log_id)

    if web.input().status not in ('closed'):
      self.raise_badrequest("Invalid status for log entry %d: %s", log_id, web.input().status)

    # Change the status
    n_updated = TicketLogLogic(log_id).set_status(web.input().status)
    if n_updated != 1:
      self.raise_badrequest("Failed to updated status for log entry %d", log_id)

    return "success"



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
    filedir = '/home/mac/test/datastore/attachments/%08d' % int(row.ticket_id)

    # Find the file in the directory
    for file in os.listdir(filedir):
      if file.startswith(row.uuid):
        web.header("Content-Type", row.mime_type)
        return open(filedir + '/' + file,"rb").read() # Notice 'rb' for reading images

    self.raise_badrequest("Resource %s not found in directory" % hashstr)

     









if __name__ == '__main__' :
  app.run()
