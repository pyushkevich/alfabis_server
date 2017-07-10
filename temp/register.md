$def with(email="", fullname="", message=None)

<script>
function validatePassword() {
  var passwd = document.getElementById("passwd");
  var passwd2 = document.getElementById("passwd2");
  if(passwd.value != passwd2.value)
    passwd2.setCustomValidity("Passwords do not match");
  else
    passwd2.setCustomValidity('');
}
</script>

New User Registration
=====

<form class="pure-form pure-form-aligned" action="/register" method="POST">
    <fieldset>
        <div class="pure-control-group">
            <label for="email">Email Address</label>
            <input id="email" type="email" name="email" placeholder="your email" value="$(email)" required> 
        </div>

        <div class="pure-control-group">
            <label for="name">Full Name</label>
            <input id="name" type="text" name="fullname" placeholder="your full name" value="$(fullname)" required>
        </div>

        <div class="pure-control-group">
            <label for="passwd">Password</label>
            <input id="passwd" type="password" name="passwd" placeholder="Password" required>
        </div>

        <div class="pure-control-group">
            <label for="passwd2">Verify Password</label>
            <input id="passwd2" type="password" name="passwd2" placeholder="Password" required oninput="validatePassword()">
        </div>

        <div class="pure-controls">
            <label for="cb" class="pure-checkbox" required>
                <input id="cb" type="checkbox"> I've read the terms and conditions
            </label>

            <button type="submit" class="pure-button pure-button-primary">Submit</button>
        </div>
    </fieldset>
</form>

$if message:
  <div style="color:red">$(message)</div>


