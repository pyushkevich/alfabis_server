$def with(tickets)

DSS Tickets Listing
=====

<div style="font-size:75%">
<table class="pure-table pure-table-bordered">
    <thead>
        <tr>
            <th>ID</th>
            <th>Service</th>
            <th>User</th>
            <th>Status</th>
            <th>Started</th>
            <th>T_Queue</th>
            <th>T_Run</th>
            <th>Progress</th>
        </tr>
    </thead>
    <tbody>
$for t in tickets:
      $if t['deleted'] is False:
        <tr style="font-weight:bold">
      $else:
        <tr>
       <td>
       <a href="/admin/tickets/$t['id']/detail" target="_blank">
       $if t['deleted']:
         <del>$t['id']</del>
       $else:
         $t['id']
       </a></td>
       <td><span style="white-space: nowrap">$t['service']</span></td>
       <td><span data-balloon="$t['email']" data-balloon-pos="up">$t['dispname']</span></td>
       <td><span style="color: $t['status_color']">$t['status']</span></td>
       <td>$t['T_init']</td>
       <td>$t['T_claim']</td>
       <td>$t['T_end']</td>
       <td>$t['progress']</td>
      </tr>

  </tbody>
</table>
</div>


