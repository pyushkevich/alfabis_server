$def with(auth_url=None, token=None)
Title: Alfabis Server


Alfabis Server 1.0 -- API Token Request
=====
$if session.loggedin == False:
  You will need a *secret token* to use the Alfabis command line tools. To generate a token, please authenticate yourself using one of the methods below:

  * [Login with Google]($(auth_url))

$else:
  You have authenticated as **$(session.email)**.  Your secret token is below. 
  Copy and paste it into your Alfabis-compatible tool.

      $(token) 
