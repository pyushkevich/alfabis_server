$def with(services)

DSS Segmentation Service Listing
=====

Defined services:

<table class="pure-table">
    <thead>
        <tr>
            <th>Name</th>
            <th>Short Description</th>
        </tr>
    </thead>
     <tbody>
$for svc in services:
         <tr>
           <td>$svc.name</td>
           <td>$svc.shortdesc</td>
         </tr>
         </tbody>
 </table>

 More services may be added in the future.
