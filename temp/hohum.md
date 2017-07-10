$def with(signed_in, log_message=None)


Alfabis Server 1.0 
=====
ALFABIS is a web-based application for medical image automated processing. You can upload images using a web-based API or directly through the website, request a certain kind of processing, and service providers will generate automated processing results. It's easy and lightweight.

$if session.loggedin == False:
  <form class="pure-form" action="/login" method="POST">
      <fieldset>
          <legend>Sign in or register for ALFABIS</legend>

          <input type="email" placeholder="Email" name="name">
          <input type="password" placeholder="Password" name="passwd">

          <label for="remember">
              <input id="remember" type="checkbox"> Remember me
          </label>

          &nbsp
          &nbsp

          <button type="submit" name="signin" class="pure-button pure-button-primary">Sign in</button>
          <button type="submit" name="register" class="pure-button">Register</button>
      </fieldset>
  </form>
$if log_message:
  <div style="color:red">$(log_message)</div>
