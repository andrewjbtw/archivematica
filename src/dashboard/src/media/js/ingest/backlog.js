window.elasticsearch_cache = {};

function renderBacklogSearchForm(openInNewTab) {
  // create new form instance, providing a single row of default data
  var search = new advancedSearch.AdvancedSearchView({
    el: $('#search_form_container'),
    rows: [{
      'op': '',
      'query': '',
      'field': '',
      'type': ''
    }],
    'deleteHandleHtml': '<img src="/media/images/delete.png" style="margin-left: 5px"/>',
    'addHandleHtml': '<a>Add New</a>'
  });

  // define op field
  var opAttributes = {
    title: 'boolean operator',
    class: 'search_op_selector'
  }
  search.addSelect('op', opAttributes, {
    'or': 'or',
    'and': 'and',
    'not': 'not'
  });

  // define query field
  search.addInput('query', {title: 'search query', 'class': 'aip-search-query-input'});

  // default field name field
  search.addSelect('field', {title: 'field name'}, {
    ''             : 'Any',
    'filename'     : 'File name',
    'file_extension': 'File extension',
    'accessionid'  : 'Accession number',
    'ingestdate'   : 'Ingest date (YYYY-MM-DD)',
    'sipuuid'      : 'SIP UUID'
  });

  // default field name field
  search.addSelect('type', {title: 'query type'}, {
    'term': 'Keyword',
    'string': 'Phrase'
  });

  // don't show first op field
  search.fieldVisibilityCheck = function(rowIndex, fieldName) {
    return rowIndex > 0 || fieldName != 'op';
  };

  // override default search state if URL parameters set
  if (search.urlParamsToData()) {
    search.rows = search.urlParamsToData();
  }

  search.render();

  function backlogSearchSubmit() {
    // Query Django, which queries ElasticSearch, to get the backlog file info
    var query_url = '/ingest/backlog/' + '?' + search.toUrlParams();
    $.get(
      query_url,
      null,
      function (data, status) {
        if (status == 'success') {
          // Cache ES response so it can be looked up from SIP arrange later
          // without needing to hit up ES a second time
          cacheBacklogData(data);
          // Originals browser from ingest_file_browser.js
          // Search information needs to go here
          originals_browser.display_data(transformElasticsearchResponse(data));
        } else {
          console.log('Failed to get transfer backlog data from '+query_url);
        }
      }
    );
  }

  function cacheBacklogData(data) {
    var record;
    for (var i in data) {
      record = data[i];
      // Clone the record, then decode the base64-encoded data to
      // match the original ES response
      var copy = $.extend({}, record);
      copy.relative_path = Base64.decode(copy.relative_path);
      window.elasticsearch_cache[record.relative_path] = copy;
    }
  }

  function transformElasticsearchResponse(data) {
    var record;
    var return_list = [];
    for (var i in data) {
      record = data[i];
      directoryToDirectoryTree(record.relative_path, return_list, record.not_draggable);
    }
    return return_list;
  }

  function directoryToDirectoryTree(path, return_list, not_draggable) {
    var parts = path.split('/');
    if (['logs', 'metadata'].indexOf(parts[0]) != -1) {
      var not_draggable = true;
    }
    if (parts.length == 1) {
      return_list.push({
        name: parts[0],
        not_draggable: not_draggable
      });
    } else {
      node = parts[0];
      others = parts.slice(1, -1).join('/');
      if (return_list.length == 0 || return_list[return_list.length - 1]['name'] != node) {
        return_list.push({
          name: node,
          not_draggable: not_draggable,
          children: []
        });
      }
      directoryToDirectoryTree(others, return_list[return_list.length - 1]['children'], not_draggable);
      return_list[return_list.length - 1]['not_draggable'] = return_list[return_list.length - 1]['not_draggable'] && not_draggable;
    }
  }

  // submit logic
  $('#search_submit').click(function() {
    backlogSearchSubmit();
  });

  $('#search_form').submit(function() {
    backlogSearchSubmit();
    return false;
  });
}
