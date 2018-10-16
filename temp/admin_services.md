$def with(pd)

DSS Providers and Services
=====

$for pid in pd.keys():
    Provider **$pid**
    -----

    **Services:**
    <div style="font-size:75%">
    <table class="pure-table pure-table-bordered">
      <thead>
        <tr>
          <th>Name</th>
          <th>Version</th>
          <th>GitHash</th>
        </tr>
      </thead>
      <tbody>
      $for s in pd[pid]['services']:
        <tr>
          <td>$s['name']</td>
          <td>$s['version']</td>
          <td>$s['githash']</td>
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
        </tr>
      </thead>
      <tbody>
      $for s in pd[pid]['users']:
        <tr>
          <td>$s['email']</td>
          <td>$s['dispname']</td>
          <td>$s['admin']</td>
        </tr>
      </tbody>
    </table>
    </div>

      



