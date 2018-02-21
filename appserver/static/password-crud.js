'use strict';

require(['jquery',
        'underscore',
        'splunkjs/mvc',
        'splunkjs/mvc/utils',
        'splunkjs/mvc/tokenutils',
        'splunkjs/mvc/messages',
        'splunkjs/mvc/searchmanager',
        '/static/app/TA-zenoss/Modal.js',
        'splunkjs/mvc/simplexml/ready!'],
function ($,
          _,
          mvc,
          utils,
          TokenUtils,
          Messages,
          SearchManager,
          Modal) {

    function runSearch() {
        var search1 = new SearchManager({
                "id": "search1",
                "cancelOnUnload": true,
                "status_buckets": 0,
                "earliest_time": "-24h@h",
                "latest_time": "now",
                "sample_ratio": 1,
                "search": "| rest /services/storage/passwords | table username, password, realm, clear_password, eai:acl.app | rename eai:acl.app as app",
                "app": utils.getCurrentApp(),
                "auto_cancel": 90,
                "preview": true,
                "tokenDependencies": {
                },
                "runWhenTimeIsUndefined": false
            }, {tokens: true, tokenNamespace: "submitted"});

        var mainSearch = splunkjs.mvc.Components.getInstance("search1");
        var myResults = mainSearch.data('results', { output_mode:'json', count:0 });

        mainSearch.on('search:progress', function(properties) {
            Messages.render("waiting", $(passwordTableDiv));
        });

        mainSearch.on('search:done', function(properties) {
            document.getElementById("password-table").innerHTML = "";

            if(properties.content.resultCount == 0) {
                console.log("No Results");
                Messages.render("no-results", $(passwordTableDiv));
                return;
            }
        });

        myResults.on("data", function() {
            var data = myResults.data().results;
            createTable(passwordTableDiv, contextMenuDiv, data);
        });
    }

    function refreshWindow() {
        location.reload()
        $('#create-user').show();
    }

    function deleteCredential(row, tableDiv) {
        var username=Splunk.util.getConfigValue("USERNAME");      
        var url = "/en-US/splunkd/__raw/servicesNS/" + username + "/" + row[3] + "/storage/passwords/" + row[2] + ":" + row[0] +":";


        var removeUser = function () {
            $.ajax({
                type: "DELETE",
                url: url,
                success: function() {
                    renderModal("user-deleted",
                                "User Deleted",
                                "<p>Successfully deleted user " + row[0] + ":" + row[2] + "</p>",
                                "Close",
                                refreshWindow) 
                },
                error: function() {
                    alert("Failed to delete user " + row[0] + ". See console for details");
                }
            });
        }

        var deleteUser = renderModal("user-delete-confirm",
                    "Confirm Delete Action",
                    "<p>You're about to remove the user " + row[0] + ":" + row[2] + " - Press ok to continue</p>",
                    "Ok",
                    removeUser); 
        console.log("deleting user" + deleteUser);
    }

    function createTable(tableDiv, contextMenuDiv, data) {
        console.log("in Scott's new module");
        console.log(data);
        var html = "";
        var tdHtml = "";
        var contextMenu = '<ul id="example1-context-menu" class="dropdown-menu"><li data-item="update"><a>Update</a></li><li data-item="delete"><a>Delete</a></li></ul>';
        var header = '<table id="rest-password-table" class="table table-striped dashboard-element table-hover">' + '<thead class="thead-default"><tr><th style><div class="th-inner "><h3>Username</h3></div><div class="fht-cell"></div></th>' + '<th style><div class="th-inner "><h3>Password</h3></div><div class="fht-cell"></div></th>' + '<th style><div class="th-inner "><h3><h3>Realm</h3></div><div class="fht-cell"></div></th>' + '<th style><div class="th-inner "><h3>App</h3></div><div class="fht-cell"></div></th>' + '<th style><div class="th-inner "><h3>Clear Password</h3></div><div class="fht-cell"></div></th></tr></thead><tbody>';
        html += header;
        _.each(data, function(row, i) {
            console.log(row);
            tdHtml += '<tr class="striped" data-index="' + i + '"><td style>' + row.username + '</td>' + '<td style>' + row.password + '</td><td style>' + row.realm + '</td><td style>' + row.app + '</td><td style>' + row.clear_password + '</td></tr>';
        });
        tdHtml += "</tbody></table";
        html += tdHtml;
        $(tableDiv).append(html);
        $(contextMenuDiv).append(contextMenu);

        $('#rest-password-table').bootstrapTable({
            contextMenu: '#example1-context-menu',
            onContextMenuItem: function(row, $el){
                if($el.data("item") == "update"){
                    $('#create-user').hide();
                    $('#update-user').show();
                    $('input[id=updateUsername]').val(row[0]);
                    $('input[id=updateRealm]').val(row[2]);
                    $('input[id=updateApp]').val(row[3]);
                } else if($el.data("item") == "delete"){
                    deleteCredential(row, tableDiv);
                }
            }
        });
    }

    function renderModal(id, title, body, buttonText, callback) {
        var myModal = new Modal(id, {
                 title: title,
                 destroyOnHide: true,
                 type: 'wide'
        }); 

        var hold = function () {
            if(reload == true) {
                location.reload();
            }
            console.log("returning");
            return true;
        }

        console.log(myModal);
        $(myModal.$el).on("hide", function(){
            // Not taking any action on hide, but you can if you want to!
        })
 
        myModal.body.append($(body));
 
        myModal.footer.append($('<button>').attr({
            type: 'button',
            'data-dismiss': 'modal'
        }).addClass('btn btn-primary mlts-modal-submit').text(buttonText).on('click', callback))

        /*
        }).addClass('btn btn-primary mlts-modal-submit').text(buttonText).on('click', function () {
            // Not taking any action on Close... but I could!        
        }))  
        */

        /*
        $(myModal.$el).promise().done(function() {
            if(reload == true) {
                location.reload();
            }
            console.log("returning");
            return true;
        });
        */

        myModal.show(); // Launch it!  
    }   

    function renderCreateUserForm() {
        var html = '<h1>Create User</h1><p>Right click on row to update or delete credentials.</p><form id="createCredential"> <div class="form-group"><label for="username">Username</label> <input type="username" class="form-control" id="createUsername" placeholder="Enter username"></div><p></p><div class="form-group"> <label for="password">Password</label> <input type="password" class="form-control" id="createPassword" placeholder="Password"></div><label for="confirmPassword">Confirm Password</label> <input type="password" class="form-control" id="createConfirmPassword" placeholder="Confirm Password"> </div> <div class="form-group"> <label for="realm">Realm</label> <input type="realm" class="form-control" id="createRealm" placeholder="Realm"><br></br></div> <button type="submit" class="btn btn-primary">Create</button> </form>'
        $('#create-user').append(html);

        $( "#createCredential" ).submit(function( event ) {
            event.preventDefault();
            var username = $('input[id=createUsername]').val();
            var password = $('input[id=createPassword]').val();
            var confirmPassword = $('input[id=createConfirmPassword]').val();
            var realm = $('input[id=createRealm]').val();

            var formData = {"name": username,
                            "password": password,
                            "realm": realm};

            if(password != confirmPassword) {
                return renderModal("password-mismatch",
                                   "Password Mismatch",
                                   "<p>Passwords do not match</b>",
                                   "Close",
                                   function(){return});
            } else {
                var currentUser = Splunk.util.getConfigValue("USERNAME");      
                var app = utils.getCurrentApp();
                var url = "/en-US/splunkd/__raw/servicesNS/" + currentUser + "/" + app + "/storage/passwords";

                $.ajax({
                    type: "POST",
                    url: url,
                    data: formData,
                    success: function() {
                        renderModal("user-added",
                                    "User Created",
                                    "<p>Successfully created user " + username + ":" + realm + "</p>",
                                    "Close",
                                    refreshWindow);
                    },
                    error: function(e) {
                        console.log(e);
                        renderModal("user-add-fail",
                                    "Failed User Creation",
                                    "<p>Failed to create user " + username + ":" + realm + "</p>",
                                    "Close",
                                    function() {return});
                    }
                });
            }
        });
    }

    function renderUpdateUserForm() {
        var html = '<h1>Update User</h1><form id="updateCredential"> <div class="form-group"><label for="username">Username</label> <input type="username" class="form-control" id="updateUsername" placeholder="Enter username"></div><p></p><div class="form-group"> <label for="password">Password</label> <input type="password" class="form-control" id="updatePassword" placeholder="Password"> </div> <label for="confirmPassword">Confirm Password</label> <input type="password" class="form-control" id="updateConfirmPassword" placeholder="Confirm Password"> </div> <div class="form-group"> <label for="realm">Realm</label> <input type="realm" class="form-control" id="updateRealm" placeholder="Realm"><br></br></div> <div class="form-group"> <input type="hidden" class="form-control" id="updateApp"></div><button type="submit" class="btn btn-primary">Update</button> </form>'
        $('#update-user').append(html).hide();

        $( "#updateCredential" ).submit(function( event ) {
            event.preventDefault();
            var username = $('input[id=updateUsername]').val();
            var password = $('input[id=updatePassword]').val();
            var confirmPassword = $('input[id=updateConfirmPassword]').val();
            var realm = $('input[id=updateRealm]').val();
            var app = $('input[id=updateApp]').val();

            var formData = {"password": password};

            if(password != confirmPassword) {
                renderModal("password-mismatch",
                            "Password Mismatch",
                            "<p>Passwords do not match. Please re-enter.<p>",
                            "Close",
                            function() { return false }); 
        } else {
            var currentUser = Splunk.util.getConfigValue("USERNAME");      
            var url = "/en-US/splunkd/__raw/servicesNS/" + currentUser + "/" + app + "/storage/passwords/" + realm + ":" + username;

            $.ajax({
                type: "POST",
                url: url,
                data: formData,
                success: function() {
                    renderModal("password-updated",
                                "Password Updated",
                                "<p>Password successfully updated for user" + username + ":" + app + "</p>",
                                "Close",
                                refreshWindow);
                    //alert("Successfully update password for user " + username + ":" + realm);
                },
                error: function(e) {
                    console.log(e);
                    renderModal("password-updated",
                                "Password Updated",
                                "<p>Failed to update password for user " + username + ". See console for details</p>",
                                "Close",
                                refreshWindow);
                }
            });
        }
        });
    }


    renderCreateUserForm();
    renderUpdateUserForm();

    var contextMenuDiv = '#context-menu';
    var passwordTableDiv = '#password-table';
    
    runSearch();

});
