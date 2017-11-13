$def with(signed_in, log_message=None, auth_url=None)
Title: Alfabis Server


Alfabis Server 1.0 
=====
ALFABIS is a web-based framework for connecting developers of medical image analysis algorithms to their users. Users send images to the server, and algorithm providers download these images, process them, and upload the results for users to retrieve. 

$if session.loggedin == False:
  * [Login with Google]($(auth_url))

$else:
  Welcome, **$(session.email)**

$if log_message:
  <div style="color:red">$(log_message)</div>
