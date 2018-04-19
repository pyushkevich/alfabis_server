$def with(services)

DSS Segmentation Service Listing
=====

<style>
.dot {
    height: 14px;
    width: 14px;
    border-radius: 50%;
    display: inline-block;
}
</style>

<table class="pure-table pure-table-bordered">
    <thead>
        <tr>
            <th>Name</th>
            <th>Short Description</th>
            <th>Status</th>
        </tr>
    </thead>
    <tbody>
$for svc in services:
      <tr>
           <td><span style="white-space: nowrap">$svc['name']</span></td>
           <td>
               <b>$svc['shortdesc']</b>&nbsp
               <a href="$svc['url']"><img src="/static/img/icons8-external_link.png" width="16" height="16" title="External link"></a>
               <p style="font-size:small; line-height: 120%;">$svc['longdesc']</p>
           </td>
           <td style="white-space: nowrap">
               <span data-balloon="Last contacted $svc['alive_min'] min ago" data-balloon-pos="up">
                 <span class="dot" style="background-color:$svc['alive_btn']"></span>
               </span>
               <span data-balloon="$svc['srate_tooltip']" data-balloon-pos="up">
                 <span class="dot" style="background-color:$svc['srate_btn']"></span>
               </span>
               <span data-balloon="Queue length: $svc['queuelen']" data-balloon-pos="up">
                 <span class="dot" style="background-color:$svc['queuelen_btn']"></span>
               </span>
               <span style="font-size:small">$svc['runtime']</span>
           </td>
      </tr>

  </tbody>
</table>
