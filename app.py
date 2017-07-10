#!/usr/bin/python
import web,sys
import markdown
import json
import auth
import os
import hashlib
import csv
import StringIO
from pprint import pprint;
from os import walk;

# Needed for session support
web.config.debug = False

# create Google app & get app ID/secret from:
# https://cloud.google.com/console
auth.parameters['google']['app_id'] = '717316152908-m929hf2oc0agvfrb42e91srdn4j6813c.apps.googleusercontent.com'
auth.parameters['google']['app_secret'] = 'NanyXsCP3txOBCtU9UeHM664'

urls = (
  r'/', 'index',
  r"/login", "LoginPage",
  r"/register", "RegisterPage",
  r"/logout", "LogoutPage",
  r"/api/login", "LoginAPI",
  r"/api/services", "ServicesAPI",
  r"/api/tickets", "TicketsAPI",
  r"/api/tickets/(\d+)/files", "TicketFilesAPI",
  r"/api/tickets/(\d+)/status", "TicketStatusAPI"
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

# =====================
# RESTful API
# =====================

def query_as_csv(qresult, fields):
  strout = StringIO.StringIO()
  csvout = csv.DictWriter(strout, fieldnames=fields, extrasaction='ignore')
  csvout.writerows(qresult)
  return strout.getvalue()


class AbstractAPI:

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
  def check_ticket_access(self, ticket_id):
    
    # Make sure we are actually logged in
    self.check_auth()

    # Check if the ticket belongs to this user
    user_id = sess.user_id
    if len(db.select("tickets",where="user_id=$user_id and id=$ticket_id",vars=locals())) == 0:
      self.raise_badrequest("Ticket %s not found for user %s" % (ticket_id,sess.user_id))

  # Check ticket status: the status must be in one of the requested statuses
  def check_ticket_status(self, ticket_id, status_list):

    # Make sure we are actually logged in
    self.check_auth()

    # Check if the ticket belongs to this user
    user_id = sess.user_id
    res = db.select("tickets",where="user_id=$user_id and id=$ticket_id",vars=locals())

    # Same as above (check access)
    if len(res) == 0:
      self.raise_badrequest("Ticket %s not found for user %s" % (ticket_id,sess.user_id))

    # Check the status
    ticket_status = res[0].status
    if ticket_status not in status_list:
      self.raise_badrequest("Ticket %s has invalid status (%s) for this operation" % (ticket_id,ticket_status))


class TicketsAPI (TicketsAPIBase):

  # List all the tickets (tickets)
  def GET(self):
    
    # The user must be logged in
    self.check_auth()

    # Select from the database
    user_id = sess.user_id
    qresult = db.query(
        ("select T.id, S.name, T.status from tickets T, services S "
         "where T.service_id = S.id and T.user_id = $user_id"),
        vars=locals());

    web.header('Content-Type','text/csv')
    return query_as_csv(qresult, ['id','name','status'])

  def POST(self):

    # The user must be logged in
    self.check_auth()

    # Get the requested service ID
    service_name = web.input().service
    service_id = db.select("services",where="name=$service_name",vars=locals())[0].id
    ticket_id = db.insert("tickets",user_id=sess.user_id,service_id=service_id,status="init")
    return ticket_id


class TicketFilesAPI (TicketsAPIBase):

  def get_file_dir(self, ticket_id):
    filedir = '/home/mac/test/datastore/tickets/%08d' % int(ticket_id)
    if not os.path.exists(filedir):
      os.makedirs(filedir)
    return filedir

  def GET(self, ticket_id):

    # Make sure we have access to this ticket
    self.check_ticket_access(ticket_id)
    
    filedir = self.get_file_dir(ticket_id)

    for (dirpath, dirnames, filenames) in walk(filedir):
      break
    
    return filenames

  def POST(self, ticket_id):

    # Make sure we have access to this ticket
    self.check_ticket_status(ticket_id, ['init'])

    # Data directory
    x = web.input(myfile={})
    print x.keys()
    # if 'file' in x.myfile and 'filename' in x.myfile:
    try:
      filedir = self.get_file_dir(ticket_id)
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
        self.check_ticket_status(ticket_id, "init")
        n = db.update("tickets", where="id = $ticket_id", status = new_status, vars=locals())
        return db.select("tickets", where="id=$ticket_id", vars=locals())[0].status;

    self.raise_badrequest("Changing ticket status to %s is not supported" % new_status)

      
    
    


if __name__ == '__main__' :
  app.run()
