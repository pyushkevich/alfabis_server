$def with(pd)

<script>

function AddServiceListener() {
  window.alert(this.responseText);
  location.reload(true);
}

function AddService() {
  var f = document.frm_add_svc;
  var xhttp = new XMLHttpRequest();
  xhttp.open("POST", `/api/admin/providers/$${f.provider.value}/services`, true);
  xhttp.setRequestHeader('Content-type', 'application/x-www-form-urlencoded');
  xhttp.addEventListener("load", AddServiceListener);
  xhttp.send(`repo=$${f.repo.value}&ref=$${f.ref.value}`);
}

function AddProviderListener() {
  window.alert(this.responseText);
  location.reload(true);
}

function AddProvider() {
  var f = document.frm_add_prv;
  var xhttp = new XMLHttpRequest();
  xhttp.open("POST", `/api/admin/providers`, true);
  xhttp.setRequestHeader('Content-type', 'application/x-www-form-urlencoded');
  xhttp.addEventListener("load", AddProviderListener);
  xhttp.send(`name=$${f.provider.value}`);
}

function AddUser() {
  var f = document.frm_add_user;
  var xhttp = new XMLHttpRequest();
  xhttp.open("POST", `/api/admin/providers/$${f.provider.value}/users`, true);
  xhttp.setRequestHeader('Content-type', 'application/x-www-form-urlencoded');
  xhttp.addEventListener("load", AddProviderListener);
  var isadmin = (f.admin.value ? 1 : 0)
  xhttp.send(`email=$${f.email.value}&admin=$${isadmin}`);
}

function DeleteProvider(prov) {
  var xhttp = new XMLHttpRequest();
  xhttp.open("GET", `/api/admin/providers/$${prov}/delete`, true);
  xhttp.setRequestHeader('Content-type', 'application/x-www-form-urlencoded');
  xhttp.addEventListener("load", AddProviderListener);
  xhttp.send();
}

function DeleteService(prov, githash) {
  var xhttp = new XMLHttpRequest();
  xhttp.open("GET", `/api/admin/providers/$${prov}/services/$${githash}/delete`, true);
  xhttp.setRequestHeader('Content-type', 'application/x-www-form-urlencoded');
  xhttp.addEventListener("load", AddProviderListener);
  xhttp.send();
}

function DeleteUser(prov, id) {
  var xhttp = new XMLHttpRequest();
  xhttp.open("GET", `/api/admin/providers/$${prov}/users/$${id}/delete`, true);
  xhttp.setRequestHeader('Content-type', 'application/x-www-form-urlencoded');
  xhttp.addEventListener("load", AddProviderListener);
  xhttp.send();
}

</script>

DSS Providers and Services
=====

<form class="pure-form pure-form-aligned" name="frm_add_prv" id="frm_add_prv" action="javascript:void(0);">
  <fieldset>
    <legend>Add New Provider</legend>
    <div class="pure-control-group">
      <label for="provider">Provider:</label>
      <input name="provider" type="text">
    </div>
    <div class="pure-controls">
      <button type="submit" class="pure-button pure-button-primary" onclick="AddProvider()">Add Provider</button>
    </div>
  </fieldset>
</form>

<form class="pure-form pure-form-aligned" id="frm_add_svc" name="frm_add_svc" action="javascript:void(0);">
  <fieldset>
    <legend>Add New Service</legend>
    <div class="pure-control-group">
      <label for="provider">Provider:</label>
      <select name="provider">
        $for pid in pd.keys():
          <option value="$pid">$pid</option>
      </select>
    </div>
    <div class="pure-control-group">
      <label for="repo">Git Repository:</label>
      <input type="url" name="repo">
    </div>
    <div class="pure-control-group">
      <label for="ref">Reference:</label>
      <input type="text" name="ref">
      <span class="pure-form-message-inline">Branch, tag, or commit</span>
    </div>
    <div class="pure-controls">
      <button type="submit" class="pure-button pure-button-primary" onclick="AddService()">Add Service</button>
      <span id="frm_add_svc_result"></span>
    </div>
  </fieldset>
</form>

<form class="pure-form pure-form-aligned" id="frm_add_user" name="frm_add_user" action="javascript:void(0);">
  <fieldset>
    <legend>Add User to Service</legend>
    <div class="pure-control-group">
      <label for="provider">Provider:</label>
      <select name="provider">
        $for pid in pd.keys():
          <option value="$pid">$pid</option>
      </select>
    </div>
    <div class="pure-control-group">
      <label for="repo">Email:</label>
      <input type="email" name="email">
    </div>
    <div class="pure-controls">
       <input name="admin" type="checkbox" value=off> Administrator</input>
    </div>

    <div class="pure-controls">
      <button type="submit" class="pure-button pure-button-primary" onclick="AddUser()">Add User</button>
    </div>
  </fieldset>
</form>

$for pid in pd.keys():
  $ cbfun="DeleteProvider('%s')" % pid
    
    Provider **$pid**
    -----

    <form class="pure-form" name="frm_del_prv_${pid}" action="javascript:void(0);">
      <fieldset>
        <button type="submit" class="pure-button pure-button-primary" onclick="$cbfun")">Delete Provider</button>
      </fieldset>
    </form>

    **Services:**
    <div style="font-size:75%">
    <table class="pure-table pure-table-bordered">
      <thead>
        <tr>
          <th>Name</th>
          <th>Version</th>
          <th>GitHash</th>
          <th></th>
        </tr>
      </thead>
      <tbody>
      $for s in pd[pid]['services']:
        $ cbfun="DeleteService('%s','%s')" % (pid, s['githash'])
        <tr>
          <td>$s['name']</td>
          <td>$s['version']</td>
          <td>$s['githash']</td>
          <td>
            <form class="pure-form" name="frm_del_svc_${pid}_${s['githash']}" action="javascript:void(0);">
              <fieldset>
                <button type="submit" class="pure-button pure-button-primary" onclick="$cbfun")">Remove</button>
              </fieldset>
            </form>
          </td>
        </tr>
      </tbody>
    </table>
    </div>

    **Users:**
    <div style="font-size:75%">
    <table class="pure-table pure-table-bordered">
      <thead>
        <tr>
          <th>Email</th>
          <th>Name</th>
          <th>Is_Admin</th>
          <th>
        </tr>
      </thead>
      <tbody>
      $for s in pd[pid]['users']:
        $ cbfun="DeleteUser('%s',%d)" % (pid, s['id'])
        <tr>
          <td>$s['email']</td>
          <td>$s['dispname']</td>
          <td>$s['admin']</td>
          <td>
            <form class="pure-form" name="frm_del_usr_${pid}_${s['email']}" action="javascript:void(0);">
              <fieldset>
                <button type="submit" class="pure-button pure-button-primary" onclick="$cbfun")">Remove</button>
              </fieldset>
            </form>
          </td>
        </tr>
      </tbody>
    </table>
    </div>

      



