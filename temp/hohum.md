$def with(signed_in, log_message=None, auth_url=None)
Title: Distributed Segmentation Service for ITK-SNAP


Distributed Segmentation Service for ITK-SNAP
=====

<div class="pure-g">
    <div class="pure-u-3-5">
    <p>DSS is a web-based framework for connecting developers of medical image analysis algorithms to their users. Users send images to the server, and algorithm providers download these images, process them, and upload the results for users to retrieve. </p>
    <p><a href="www.itksnap.org">ITK-SNAP</a> and accompanying command-line tools are used to communicate with the DSS. </p>
    </div>
    <div class="pure-u-2-5">
    <img src="/static/img/dss_arch.png" class="pure-img">
    </div>
</div>


$if session.loggedin == False:
  <a href="$(auth_url)" class="googlebutton" title="Login with Google"></a>

$else:
  You are signed in as **$(session.email)**

$if log_message:
  <div style="color:red">$(log_message)</div>
