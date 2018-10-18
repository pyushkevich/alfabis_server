Title: DSS Admin Home

<script>
function SimpleListener() {
    window.alert(this.responseText)
}

function RebuildCatalog() {
    var xhttp = new XMLHttpRequest();
    xhttp.open("POST", "/api/admin/catalog/rebuild", true);
    xhttp.setRequestHeader("Content-type", "application/json");
    xhttp.addEventListener("load", SimpleListener);
    xhttp.send();
}

function PurgeTickets() {
    var x = document.frm_purge
    var url = "/api/admin/tickets/purge/completed"
    if (x.all.checked) {
        url = "/api/admin/tickets/purge/all"
    }
    var xhttp = new XMLHttpRequest();
    xhttp.open("POST", url, true);
    xhttp.addEventListener("load", SimpleListener);
    xhttp.send("days=" + x.days.value);
}
</script>

DSS Administrator Home
=====

Maintenance Tasks
-----

<form class="pure-form" name="frm_purge" action="javascript:void(0);">
    <fieldset>
        <legend>Purge tickets</legend>
        <label for="days">Days:</label>
        <input type="number" name="days" min="1" max="7" value="7">
        <label for="all">
            <input name="all" type="checkbox" value=off> Include open tickets</input>
        </label>
        <button type="button" class="pure-button pure-button-primary" onclick="PurgeTickets()">Purge</button>
    </fieldset>
</form>
