require(['jquery',
    'underscore',
    'splunkjs/mvc/utils',
    'splunkjs/mvc/tableview',
    'splunkjs/mvc/simplexml/ready!'
    ], function ($, _, utils, TableView) {

        var splunkWebHttp = new splunkjs.SplunkWebHttp();
        var service = new splunkjs.Service(splunkWebHttp);
        var storagePasswords = service.storagePasswords({ 
            owner: Splunk.util.getConfigValue("USERNAME"),
            app: utils.getCurrentApp()
        });

        //Add click listeners to action buttons in table
        function pollAvailability() {
            //Are action buttons already rendered in the table?
            if ($("td button").length > 1) {

                $('.editBtn').on("click", function (e) {
                    var cells = $(this).parent("td").parent().find("td");
                    //Careful! Changing the fields sorting of the restsearch might lead to errors here!
                    $("#input_form_username").val(cells.get(0).textContent);
                    $("#input_form_realm").val(cells.get(3).textContent);

                    //Style modal opportunely
                    $("#createModal .modal-header h3").text("Update User");
                    $("#input_form_username").prop("disabled", true);
                    $("#input_form_realm").prop("disabled", true);
                    //Show modal
                    $("#createModal").modal('show');
                });

                $('.delBtn').on("click", function (e) {
                    var cells = $(this).parent("td").parent().find("td");
                    //Careful! Changing the fields sorting of the restsearch might lead to errors here!
                    var username = cells.get(0).textContent;
                    var realm = cells.get(3).textContent;
                    var myStorageName = realm + ":" + username + ":";

                    if (confirm("Are you sure you want to remove user " + myStorageName + "?")) {
                        storagePasswords.fetch(function (err, storagePasswords) {
                            if (err) { console.warn(err); }
                            else {
                                // var list = storagePasswords.list();
                                // console.log("Found " + list.length + " storage passwords");
                                var myStorageObj = storagePasswords.item(myStorageName);
                                //Determine whether the storage password exists before deleting it
                                if (!myStorageObj) {
                                    alert("There is no storage password named '" + myStorageName + "'");
                                } else {
                                    myStorageObj.remove();
                                    console.log("Deleted the storage password '" + myStorageName + "'");
                                    //Auto-run the search below for convenience
                                    splunkjs.mvc.Components.getInstance("restsearch").startSearch();

                                    setTimeout(pollAvailability, 600);
                                }
                            }
                        });
                    }
                });

            } else {
                // console.log("Polling again 200ms more");
                setTimeout(pollAvailability, 200);
            }
        };

        //Listener on "Create" button click
        $("#btn_create").on("click", function () {
            //Style modal opportunely
            $("#createModal .modal-header h3").text("Create User");
            $("#createModal .modal-body input").val("");
            $("#input_form_username").prop("disabled", false);
            $("#input_form_realm").prop("disabled", false);
            //Show modal
            $("#createModal").modal("show");
        });

        //Listener on modal "close" click
        $("#showPwdModal .modal-header .close").on("click", function () {
            //To keep DOM clean from clear text passwords
            $("#showPwdModal .modal-body p").text("********");
        });

        //Listener on "Save" button click
        $("#btn_save").on("click", function () {
            var username = $("#input_form_username").val();
            var password = $("#input_form_password").val();
            var realm = $("#input_form_realm").val();

            if (username === "") {
                alert("Missing username - Please enter a username to create a user");
            } else if (password === "") {
                alert("Missing password - Please enter a password to create a user");
            } else if (password != $("#input_form_confirm_password").val()) {
                alert("Password mismatch - Passwords do not match!");
            
            } else {
                var title = $("#createModal .modal-header h3").text();
                if (title.indexOf('Update') === -1) {
                    // console.log("Creating a new storage password");
                    storagePasswords.create({
                        name: username,
                        realm: realm,
                        password: password
                    },
                        function (err, storagePassword) {
                            if (err) { 
                                console.log(err);
                            } else {
                                // console.log(storagePassword.properties());
                                //Auto-run the search below for convenience
                                splunkjs.mvc.Components.getInstance("restsearch").startSearch();
                                //Close modal
                                $("#createModal").modal('hide');

                                setTimeout(pollAvailability, 600);
                            }
                        });
                
                } else {
                    // console.log("Updating an existing storage password");
                    var myStorageName = realm + ":" + username + ":";
                    storagePasswords.fetch(function (err, storagePasswords) {
                        if (err) { console.warn(err); }
                        else {
                            // var list = storagePasswords.list();
                            // console.log("Found " + list.length + " storage passwords");
                            var myStorageObj = storagePasswords.item(myStorageName);
                            //Determine whether the storage password exists before updating it
                            if (!myStorageObj) {
                                alert("There is no storage password named '" + myStorageName + "'");
                            } else {
                                myStorageObj.update({
                                    password: password
                                });
                                console.log("Updated the storage password '" + myStorageName + "'");
                                //Auto-run the search below for convenience
                                splunkjs.mvc.Components.getInstance("restsearch").startSearch();
                                //Close modal
                                $("#createModal").modal('hide');

                                setTimeout(pollAvailability, 600);
                            }
                        }
                    });
                }
            }
        });

        //Give time to load the table (if there's one) or onclick will not apply to Action buttons
        if ($("#resttable td").length > 0) {
            setTimeout(pollAvailability, 600);
        }

        //Add custom view rendering
        var CustomActionsRenderer = TableView.BaseCellRenderer.extend({
            canRender: function (cell) {
                //Enable this custom cell renderer for more field
                return _(["clear_password", "more_actions"]).contains(cell.field);
            },
            render: function ($td, cell) {

                if (cell.field === "more_actions") {
                    var strHtml = "<button type='button' class='btn btn-pill icon-pencil editBtn'/>";
                    strHtml += "<button type='button' class='btn btn-pill icon-trash delBtn'/>";
                    //Add TextBox With Specific Style
                    $td.append(strHtml);
                } else {
                    var strHtml = '<button type="button" class="btn btn-pill icon-visible showBtn" onclick="' +
                        '$(\'#showPwdModal .modal-body p\').text(\'' + cell.value + '\');' +
                        '$(\'#showPwdModal\').modal(\'show\');"/>';
                    //Add TextBox With Specific Style
                    $td.append(strHtml);
                }
            }
        });

        //Add custom cell renderers so that the table will re-render automatically on page load
        splunkjs.mvc.Components.get('resttable').getVisualization(function (tableView) {
            tableView.addCellRenderer(new CustomActionsRenderer());
        });

    }
);