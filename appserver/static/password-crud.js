'use strict';

require(['jquery',
        'underscore',
        'splunkjs/mvc',
        'splunkjs/mvc/utils',
        'splunkjs/mvc/tokenutils',
        'splunkjs/mvc/messages',
        'splunkjs/mvc/searchmanager',
        'splunkjs/mvc/simplexml/ready!'],
function ($,
          _,
          mvc,
          utils,
          TokenUtils,
          Messages,
          SearchManager) {

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

    function deleteCredential(row, tableDiv) {
        var username=Splunk.util.getConfigValue("USERNAME");      
        var url = "/en-US/splunkd/__raw/servicesNS/" + username + "/" + row[3] + "/storage/passwords/" + row[2] + ":" + row[0] +":";
        var deleteUser = confirm("You're about to delete user " + row[0] + ". Press ok to continue");

        if(deleteUser) { 
            $.ajax({
                type: "DELETE",
                url: url,
                success: function() {
                    alert("Successfully deleted user " + row[0] + ":" + row[2]);
                    location.reload(); 
                },
                error: function() {
                    alert("Failed to add user " + row[0] + ". See console for details");
                }
            });
        }
    }

    function createTable(tableDiv, contextMenuDiv, data) {
        console.log("in Scott's new module");
        console.log(data);
        var html = "";
        var tdHtml = "";
        var contextMenu = '<ul id="example1-context-menu" class="dropdown-menu"><li data-item="update"><a>Update</a></li><li data-item="delete"><a>Delete</a></li></ul>';
        var header = '<table id="rest-password-table" class="table dashboard-element table-hover">' + '<thead><tr><th style><div class="th-inner ">Username</div><div class="fht-cell"></div></th>' + '<th style><div class="th-inner ">Password</div><div class="fht-cell"></div></th>' + '<th style><div class="th-inner ">Realm</div><div class="fht-cell"></div></th>' + '<th style><div class="th-inner ">App</div><div class="fht-cell"></div></th>' + '<th style><div class="th-inner ">Clear Password</div><div class="fht-cell"></div></th></tr></thead><tbody>';
        html += header;
        _.each(data, function(row, i) {
            console.log(row);
            tdHtml += '<tr class="striped" data-index="' + i + '"><td style>' + row.username + '</td>' + '<td style>' + row.password + '</td><td style>' + row.realm + '</td><td style>' + row.app + '</td><td style>' + row.clear_password + '</td></tr>';
            //console.log(row);
            //$(div).append(tdHtml);
        });
        tdHtml += "</tbody></table";
        html += tdHtml;
        $(tableDiv).append(html);
        $(contextMenuDiv).append(contextMenu);

        $('#rest-password-table').bootstrapTable({
            contextMenu: '#example1-context-menu',
            onContextMenuItem: function(row, $el){
                if($el.data("item") == "update"){
                    console.log(row);
                    
                } else if($el.data("item") == "delete"){
                    console.log(row);
                    deleteCredential(row, tableDiv);
                }
            }
        });
    }


    var contextMenuDiv = '#context-menu';
    var passwordTableDiv = '#password-table';
    //var username=Splunk.util.getConfigValue("USERNAME");      
    //console.log(username);

    /*
    var restPasswordSearch = new SearchManager({
        id: "restPasswordSearch",
        cancelOnUnload: true,
        preview: true,
        //cache: true,
        status_buckets: 0,
        app: utils.getCurrentApp(),
        search: "| rest /services/storage/passwords | table username, password, realm, clear_password",
        tokenDependencies: {
        },
        runWhenTimeIsUndefined: true
    }, {tokens: true, tokenNamespace: "submitted"});
    */

    runSearch();
    //console.log(data);
    //createTable(passwordTableDiv, contextMenuDiv, data);

    /*
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
        console.log(data);
        createTable(passwordTableDiv, contextMenuDiv, data);
    });
    */

});
