/*global $*/
/*eslint no-undef: "error"*/

$(document).ready(function () {
  
  function newReflex() {
    $.ajax({
      url: '/newreflexdialog',
      data: {},
      dataType: 'html',
      success: newReflexDialog
    });
  }
  
  function newReflexDialog(data) {
    $('#dialogs').append(data);
    $('#newreflex').dialog({
      title: 'Add New Reflex',
      buttons: [{
        text: 'Add',
        click: addNewReflex
      },
      {
        text: 'Cancel',
        click: function() {
          console.log('Cancel');
          $(this).dialog('close');
        }
      }]
    });
  }
  
  function addNewReflex() {
    var langid = $('#langid').val();
    var sourceid = $('#sourceid').val();
    var form = $('#form').val();
    var gloss = $('#gloss').val();
    console.log('gloss: ' + gloss)
    $.ajax({
      type: 'GET',
      url: '/addnewreflex',
      data: {
        langid: langid,
        sourceid: sourceid,
        form: form,
        gloss: gloss
      },
      dataType: 'json'
    });
    reflexes.ajax.reload();
    console.log('Insert langid:' + langid + ' sourceid:' + sourceid + ' form:' + form + ' gloss:' + gloss);
    $(this).dialog('close');
  }
  
  //////////////////////////////////////////
  // Add reflexes to cognate sets
  //////////////////////////////////////////
  
  function addReflexesToSupportingForms() {
    var refSelection = reflexes
    .rows({
      selected: true
    })
    .data();
    var protoSelection = protoforms
    .rows({
      selected: true
    })
    .data();
    for (var i = 0; i < refSelection.length; i++) {
      for (var j = 0; j < protoSelection.length; j++) {
        var refid = refSelection[i][1];
        var prefid = protoSelection[j][0];
        var plangid = protoSelection[j][1];
        console.log('Adding ' + refid + ' to ' + prefid + ' in ' + plangid)
        $.ajax({
          url: '/addsupporting',
          data: {
            refid: refid,
            prefid: prefid,
            plangid: plangid
          },
          dataType: 'html',
          success: popupSupportingDialog,
          context: {
            refid: refid,
            prefid: prefid,
            plangid: plangid,
            morph_index: 0
          }
        });
      }
    }
  }
  
  //////////////////////////////////////////
  // Add potential cognates to cognate sets
  //////////////////////////////////////////

  function addPotCogsToSupportingForms() {
    var refSelection = potcogs
    .rows({
      selected: true
    })
    .data();
    var protoSelection = protoforms
    .rows({
      selected: true
    })
    .data();
    for (var i = 0; i < refSelection.length; i++) {
      for (var j = 0; j < protoSelection.length; j++) {
        var refid = refSelection[i][1];
        var prefid = protoSelection[j][0];
        var plangid = protoSelection[j][1];
        console.log('Adding ' + refid + ' to ' + prefid + ' in ' + plangid)
        $.ajax({
          url: '/addsupporting',
          data: {
            refid: refid,
            prefid: prefid,
            plangid: plangid
          },
          dataType: 'html',
          success: popupSupportingDialog,
          context: {
            refid: refid,
            prefid: prefid,
            plangid: plangid,
            morph_index: 0
          }
        });
      }
    }
  }

  //////////////////////////////////////////
  // Remove reflexes from cognate sets
  //////////////////////////////////////////
  
  function removeSupportingFormFromSet() {
    console.log('Remove reflex');
    var supportingSelection = supporting
    .rows({
      selected: true
  })
    .data();
    var protoSelection = protoforms
    .rows({
      selected: true
    })
    .data();
    for (var i = 0; i < supportingSelection.length; i++) {
      var refid = supportingSelection[i][0]; // Check that refid is in the first field
      var form = supportingSelection[i][2];
      var gloss = supportingSelection[i][3];
      var prefid = protoSelection[0][0];
      console.log('Removing ' + refid + ' ' + form + ' ' + gloss + 'from cognate set ' + prefid);
      $.ajax({
        url: '/removesupporting',
        data: {
          refid: refid,
          prefid: prefid
        },
        datatype: 'json',
        success: reloadSupporting,
        context: {
          refid: refid,
          prefid: prefid,
        }
      });
    }
  }
  
  function reloadSupporting() {
    supporting.ajax.reload();
  }

  //////////////////////////////////////////
  // Edit reflexes
  //////////////////////////////////////////
  
  function editReflexes() {
    var selection = reflexes.rows({
      selected: true
    }).data();
    for (var i = 0; i < selection.length; i++) {
      $.ajax({
        refid: selection[i][1],
        url: '/reflexdialog',
        data: {
          langid: selection[i][0],
          refid: selection[i][1],
          lname: selection[i][2],
          form: selection[i][3],
          gloss: selection[i][4],
        },
        dataType: 'html',
        success: editReflexDialog
      });
    }
  }
  
  function editReflexDialog(data) {
    var refid = this.refid;
    $('#dialogs').append(data);
    console.log('#edit' + refid + ' reflex');
    $('#edit' + refid).data('refid', refid).dialog({
      title: 'Edit Reflex',
      buttons: [{
        text: 'Update',
        click: updateReflex
      },
      {
        text: 'Cancel',
        click: function() {
          console.log('Cancel');
          $(this).dialog('close');
        }
      }
    ]
  });
  }

  function updateReflex() {
    var refid = $(this).data('refid');
    var form = $('#editform' + refid).val();
    var gloss = $('#editgloss' + refid).val();
    $.ajax({
      type: 'GET',
      url: '/updatereflex',
      data: {
        refid: refid,
        form: form,
        gloss: gloss
      },
      dataType: 'json'
    });
    reflexes.ajax.reload();
    console.log('Update ' + refid + ' ' + form + ' ' + gloss);
    $(this).dialog('close');
  }

  //////////////////////////////////////////
  // Find Potential Cognates
  //////////////////////////////////////////

  function findPotCogs() {
    var selection = reflexes.rows({
      selected: true
    }).data();
    // Data columns: [0]=langid, [1]=refid, [2]=lname, [3]=ipaform, [4]=gloss, [5]=is_supporting, [6]=form
    console.log('Searching for matches: ' + selection[0][3] + ' (IPA) with gloss ' + selection[0][4]);
    $.ajax({
      refid: selection[0][1],
      url: '/findpotcogs',
      data: {
        langid: selection[0][0],
        refid: selection[0][1],
        lname: selection[0][2],
        ipaform: selection[0][3],  // Use normalized IPA form for similarity
        gloss: selection[0][4],
      },
      dataType: 'html',
      success: updatePotCogs
    });
  }

  function updatePotCogs() {
    potcogs.ajax.reload();
  }

  //////////////////////////////////////////
  // Delete reflexes
  //////////////////////////////////////////

  function deleteReflexes() {
    reflexes
    .rows({
      selected: true
    })
    .data()
    .toArray()
    .forEach(function(value) {
      var refid = value[0];
      $.ajax({
        url: '/deletereflex',
        data: {
          refid: refid
        },
        success: function() {
          console.log('Deleted reflex');
          reflexes.ajax.reload();
        }
      });
    });
  }

  ///////////////////////////////////////////////////////////////////////////////
  // Add cognate sets
  ///////////////////////////////////////////////////////////////////////////////

  function newSet() {
    var selection = reflexes.rows({
      selected: true
    }).data();
    var etymon = selection[0];
    if (typeof etymon !== 'undefined') {
      console.log('etymon[2]=' + etymon[2])
      $.ajax({
        refid: etymon[0],
        url: '/newsetdialog',
        data: {
          langid: etymon[0],
          refid: etymon[1],
          lname: etymon[2],
          form: etymon[3],
          gloss: etymon[4]
        },
        dataType: 'html',
        success: newSetDialog
      });
    }
  }

  function newSetDialog(data) {
    var refid = this.refid;
    $('#dialogs').append(data);
    $('#newset').data('refid', refid).dialog({
      title: 'New Correspondence Set',
      buttons: [{
        text: 'Add',
        click: addNewSet
      },
      {
        text: 'Cancel',
        click: function() {
          console.log('Cancel');
          $(this).dialog('close');
        }
      }]
    })
  }

  function addNewSet() {
    var refid = $(this).data('refid');
    var protoform = $('#protoform').val();
    var protogloss = $('#protogloss').val();
    var plangid = $('#plangid').val();
    var morph_index = $('#morph_index').val();
    $.ajax({
      type: 'GET',
      url: '/addnewset',
      data: {
        refid: refid,
        plangid: plangid,
        protoform: protoform,
        protogloss: protogloss,
        morph_index: morph_index
      },
      dataType: 'json'
    });
    protoforms.ajax.reload();
    console.log('Added new set:' + ' protoform: ' + protoform + ' protogloss: ' + protogloss);
    $(this).dialog('close');
  }

  //////////////////////////////////////////
  // Edit protoforms
  //////////////////////////////////////////

  function editProtoform() {
    var selection = protoforms.rows({
      selected: true
    }).data();
    for (var i = 0; i < selection.length; i++) {
      $.ajax({
        refid: selection[i][0],
        url: '/reflexdialog',
        data: {
          refid: selection[i][0],
          lname: selection[i][2],
          form: selection[i][3],
          gloss: selection[i][4],
        },
        dataType: 'html',
        success: editProtoformDialog
      });
    }
  }

  function editProtoformDialog(data) {
    var refid = this.refid;
    $('#dialogs').append(data);
    $('#edit' + refid).data('refid', refid).dialog({
      title: 'Edit Protoform',
      buttons: [{
        text: 'Update',
        click: function() {
          var dlgRefid = $(this).data('refid');
          var form = $('#editform' + dlgRefid).val();
          var gloss = $('#editgloss' + dlgRefid).val();
          var dialogToClose = $(this);
          $.ajax({
            type: 'GET',
            url: '/updatereflex',
            data: {
              refid: dlgRefid,
              form: form,
              gloss: gloss
            },
            dataType: 'json',
            success: function() {
              protoforms.ajax.reload();
              supporting.ajax.reload();
              dialogToClose.dialog('close');
            },
            error: function() {
              dialogToClose.dialog('close');
            }
          });
        }
      },
      {
        text: 'Cancel',
        click: function() {
          $(this).dialog('close');
        }
      }]
    });
  }

  //////////////////////////////////////////
  // Edit morphs of supporting forms
  //////////////////////////////////////////

  function editMorphOfSupportingForm() {
    console.log('Choosing Morph');
    var protoSelection = protoforms.rows({
      selected: true
    }).data();
    var supSelection = supporting.rows({
      selected: true
    }).data();
    var prefid = protoSelection[0][0];
    var plangid = protoSelection[0][1];
    for (var i = 0; i < supSelection.length; i++) {
      var refid = supSelection[i][0];
      var morph_index = supSelection[i][4];
      console.log('Editing ' + refid + ' reflex of ' + prefid + ' in ' + plangid);
      $.ajax({
        url: '/addsupporting',
        data: {
          refid: refid,
          prefid: prefid,
          plangid: plangid
        },
        dataType: 'html',
        success: popupSupportingDialog,
        context: {
          refid: refid,
          prefid: prefid,
          plangid: plangid,
          morph_index: morph_index
        }
      });
    }
  }

  function popupSupportingDialog(html) {
    $('#dialogs').append(html);
    var refid = this.refid;
    var prefid = this.prefid;
    var plangid = this.plangid;
    var dialog = $('#supporting' + refid);
    var morphsContainer = $('#morphs-container-' + refid);
    
    dialog.data('morph_index', this.morph_index);
    
    // Setup morph click handlers
    function setupMorphClickHandlers() {
      var morphs = morphsContainer.find('.morph-span');
      morphs.off('click').on('click', function() {
        var clickedIndex = parseInt($(this).data('index'));
        morphs.removeClass('selected-morph');
        $(this).addClass('selected-morph');
        dialog.data('morph_index', clickedIndex);
        console.log('morph_index in click: ' + clickedIndex);
      });
    }
    setupMorphClickHandlers();
    
    // Setup Update Form button
    $('#update-form-btn-' + refid).on('click', function() {
      var newIpaform = $('#ipaform-input-' + refid).val();
      $.ajax({
        url: '/updateipaform',
        data: {
          refid: refid,
          ipaform: newIpaform
        },
        success: function(response) {
          console.log('Form updated successfully');
          // Update the morphs display with new morphs
          var morphsHtml = '';
          for (var i = 0; i < response.morphs.length; i++) {
            var selectedClass = (i === 0) ? ' selected-morph' : '';
            morphsHtml += '<span id="morph-' + refid + '-' + i + '" class="morph-span' + selectedClass + '" data-index="' + i + '">' + response.morphs[i] + '</span>';
          }
          morphsContainer.html(morphsHtml);
          dialog.data('morph_index', 0);
          setupMorphClickHandlers();
          // Also reload supporting table to show updated form
          supporting.ajax.reload();
        }
      });
    });
    
    dialog.dialog({
      title: 'Edit Form and Select Morph',
      width: 420,
      buttons: [{
        text: 'OK',
        click: updateMorphSelection({
          refid: refid,
          prefid: prefid,
          plangid: plangid,
          dialog: dialog
        }),
      }],
    });
  }

  function updateMorphSelection(params) {
    return function() {
      console.log('morph_index in update:' + params.dialog.data('morph_index'));
      $.ajax({
        url: '/updatemorph',
        data: {
          refid: params.refid,
          prefid: params.prefid,
          morph_index: params.dialog.data('morph_index')
        },
        success: function() {
          console.log('Update success. params.refid=' + params.refid);
          params.dialog.dialog('close');
          supporting.ajax.reload();
        }
      })
    }
  }

  //////////////////////////////////////////
  // Delete protoforms
  //////////////////////////////////////////

  function deleteProtoform() {
    protoforms
    .rows({
      selected: true
    })
    .every(function() {
      var prefid = this.data()[0];
      console.log('Deleting prefid:' + prefid);
      $.ajax({
        url: '/deleteprotoform',
        data: {
          prefid: prefid
        },
        success: function() {
          console.log('Deleted protoform');
          protoforms.ajax.reload();
          supporting.ajax.reload();
        }
      });
    });
  }

  ////////////////////////////////////////
  // Data tables
  ////////////////////////////////////////

  // Store refids filter for protoforms table (empty = show all)
  var protoformsRefidsFilter = '';

  var protoforms = $('#protoforms').DataTable({
    dom: 'Brtip',
    select: {
      style: 'single'
    },
    scrollY: '250px',
    scrollCollapse: true,
    paging: true,
    pageLength: 50,
    deferRender: true,
    columnDefs: [
      {
        targets: [1],
        visible: false,
        searchable: false
      },
      {
        targets: [0],
        visible: false
      }
    ],
    serverSide: true,
    ajax: {
      url: "/protoforms",
      type: "GET",
      data: function(d) {
        d.refids = protoformsRefidsFilter;
      }
    },
    buttons: [
      {
        text: 'New Set from Reflex',
        action: newSet
      },
      {
        text: 'Edit',
        action: editProtoform
      },
      {
        text: 'Delete',
        action: deleteProtoform
      },
      {
        text: 'Show All',
        action: function() {
          protoformsRefidsFilter = '';
          protoforms.ajax.reload();
        }
      }
    ]
  });

  var reflexes = $('#reflexes').DataTable({
      dom: 'Brtip',
      select: true,
      serverSide: true,
      scrollY: '250px',
      scrollCollapse: true,
      paging: true,
      pageLength: 50,
      deferRender: true,
      ajax: {
        url: "/reflexes",
        type: "GET"
      },
      buttons: [
        {
          text: 'Add to Set',
          action: addReflexesToSupportingForms
        },
        {
          text: "New",
          action: newReflex
        },
        {
          text: 'Edit',
          action: editReflexes
        },
        {
          text: 'Delete',
          action: deleteReflexes
        },
        {
          text: 'Potential Cognates',
          action: findPotCogs
        },
        {
          text: 'Protoforms',
          action: function() {
            // Get selected reflex ids and filter protoforms table
            var selection = reflexes.rows({ selected: true }).data().toArray();
            if (selection.length === 0) {
              alert('Please select one or more reflexes first.');
              return;
            }
            // data[1] is refid
            var refids = selection.map(function(row) { return row[1]; });
            protoformsRefidsFilter = refids.join(',');
            protoforms.ajax.reload();
          }
        }
      ],
      columnDefs: [{
        targets: [0, 1, 5, 6],  // Hide langid, refid, is_supporting, and ipaform columns
        visible: false,
      }],
      createdRow: function(row, data, dataIndex) {
        // data[5] is is_supporting (1 if in cognate set, 0 otherwise)
        if (data[5] === 1) {
          $(row).css('font-weight', 'bold');
        }
      }
    });
    
    var potcogs = $('#potcogs').DataTable({
      dom: 'Brtip',
      select: true,
      serverSide: true,
      scrollY: '250px',
      scrollCollapse: true,
      paging: true,
      pageLength: 50,
      deferRender: true,
      ajax: {
        url: "/potcogs",
        type: "GET"
      },
      buttons: [
        {
          text: "Add to Set",
          action: addPotCogsToSupportingForms
        }
      ],
      columnDefs: [{
        targets: [0, 1, 5],
        visible: false
      }]
    });
    
    var supporting = $('#supporting').DataTable({
      dom: 'Brtip',
      select: true,
      serverSide: true,
      scrollY: '250px',
      scrollCollapse: true,
      paging: true,
      pageLength: 50,
      deferRender: true,
      columnDefs: [{
        targets: [4],
        visible: false,
        searchable: false
      }],
      ajax: {
        url: "/supporting",
        type: "GET",
        data: function(d) {
          d.prefid = $('#protoforms').data('prefid') || -1;
        }
      },
      buttons: [
        {
          text: 'Edit',
          action: editMorphOfSupportingForm
        },
        {
          text: 'Remove from Set',
          action: removeSupportingFormFromSet
        }
      ]
    });
    
    ////////////////////////////////////////
    // Regex filter setup for all tables
    ////////////////////////////////////////
    
    // Helper to validate regex
    function isValidRegex(pattern) {
      if (!pattern) return true;
      try {
        new RegExp(pattern);
        return true;
      } catch (e) {
        return false;
      }
    }
    
    // Setup filter inputs for a table - server-side filtering with debounce
    // Note: DataTables with scrollY moves thead into a wrapper, so we use the wrapper selector
    function setupColumnFilters(table, tableId) {
      var debounceTimers = {};
      var wrapper = $('#' + tableId + '_wrapper');
      
      wrapper.on('input', 'input.column-filter', function() {
        var input = $(this);
        var colIdx = parseInt(input.data('column'));
        var value = input.val();
        
        // Clear existing timer for this column
        if (debounceTimers[colIdx]) {
          clearTimeout(debounceTimers[colIdx]);
        }
        
        // Debounce: wait 300ms after last keystroke before filtering
        debounceTimers[colIdx] = setTimeout(function() {
          table.column(colIdx).search(value).draw();
        }, 300);
      });
      
      // Also filter immediately on Enter key
      wrapper.on('keypress', 'input.column-filter', function(e) {
        if (e.which === 13) {  // Enter key
          e.preventDefault();  // Prevent form submission
          var input = $(this);
          var colIdx = parseInt(input.data('column'));
          var value = input.val();
          
          // Clear any pending debounce timer
          if (debounceTimers[colIdx]) {
            clearTimeout(debounceTimers[colIdx]);
          }
          
          table.column(colIdx).search(value).draw();
        }
      });
    }
    
    setupColumnFilters(reflexes, 'reflexes');
    setupColumnFilters(potcogs, 'potcogs');
    setupColumnFilters(protoforms, 'protoforms');
    setupColumnFilters(supporting, 'supporting');
    
    protoforms.on('select', function(e, dt, type, indexes) {
      var prefid = protoforms.rows(indexes).data().toArray()[0][0];
      $('#protoforms').data('prefid', prefid);
      supporting.draw();
    });
    
    //////////////////////////////////////////
    // Correspondence Sets Dialog
    //////////////////////////////////////////
    
    $('#correspondence-sets-btn').click(function() {
      $.ajax({
        url: '/correspondence_sets_dialog',
        dataType: 'html',
        success: function(html) {
          $('#dialogs').append(html);
          
          // Load proto-languages dropdown
          $.ajax({
            url: '/protolanguages',
            dataType: 'json',
            success: function(data) {
              var select = $('#protolang-select');
              data.forEach(function(lang) {
                select.append($('<option>', {
                  value: lang.langid,
                  text: lang.name
                }));
              });
            }
          });
          
          // Create dialog
          $('#correspondence-sets-dialog').dialog({
            title: 'Correspondence Sets',
            width: 900,
            height: 650,
            modal: false,
            close: function() {
              $(this).dialog('destroy').remove();
            }
          });
          
          // Load button handler
          $('#load-corr-sets-btn').click(function() {
            var plangid = $('#protolang-select').val();
            if (!plangid) {
              alert('Please select a proto-language first.');
              return;
            }
            loadCorrespondenceSets(plangid);
          });
        }
      });
    });
    
    function loadCorrespondenceSets(plangid) {
      $('#corr-loading').show();
      $('#corr-sets-container').html('<p class="corr-placeholder">Loading...</p>');
      
      $.ajax({
        url: '/correspondence_sets',
        data: { plangid: plangid },
        dataType: 'json',
        success: function(data) {
          $('#corr-loading').hide();
          renderCorrespondenceSets(data);
        },
        error: function(xhr) {
          $('#corr-loading').hide();
          $('#corr-sets-container').html(
            '<p class="corr-placeholder">Error loading correspondence sets: ' + 
            (xhr.responseJSON ? xhr.responseJSON.error : 'Unknown error') + '</p>'
          );
        }
      });
    }
    
    // Store correspondence data for sorting/filtering
    var corrData = null;
    var corrSortState = { column: null, direction: 'asc' };
    var corrFilters = {};
    
    function renderCorrespondenceSets(data) {
      var container = $('#corr-sets-container');
      container.empty();
      
      if (!data.correspondence_sets || data.correspondence_sets.length === 0) {
        container.html('<p class="corr-placeholder">No correspondence sets found.</p>');
        return;
      }
      
      // Store data for sorting/filtering
      corrData = data;
      corrSortState = { column: null, direction: 'asc' };
      corrFilters = {};
      
      var table = $('<table class="corr-set-table">');
      var thead = $('<thead>');
      
      // Header row with language names (clickable for sorting)
      var headerRow = $('<tr class="corr-header-row">');
      headerRow.append('<th></th>'); // expand icon column
      data.languages.forEach(function(lang, colIdx) {
        var th = $('<th class="sortable-header" data-col="' + colIdx + '" data-type="lang">')
          .text(lang)
          .append('<span class="sort-indicator"></span>');
        headerRow.append(th);
      });
      var countTh = $('<th class="sortable-header" data-col="count" data-type="count">')
        .text('Count')
        .append('<span class="sort-indicator"></span>');
      headerRow.append(countTh);
      thead.append(headerRow);
      
      // Filter row with regex inputs
      var filterRow = $('<tr class="corr-filter-row">');
      filterRow.append('<td></td>'); // expand icon column
      data.languages.forEach(function(lang, colIdx) {
        var td = $('<td>');
        var input = $('<input type="text" class="corr-filter-input" data-col="' + colIdx + '" placeholder="regex">')
          .on('input', function() {
            applyCorrespondenceFilters();
          });
        td.append(input);
        filterRow.append(td);
      });
      // Count filter
      var countTd = $('<td>');
      var countInput = $('<input type="text" class="corr-filter-input" data-col="count" placeholder="regex">')
        .on('input', function() {
          applyCorrespondenceFilters();
        });
      countTd.append(countInput);
      filterRow.append(countTd);
      thead.append(filterRow);
      
      table.append(thead);
      
      var tbody = $('<tbody class="corr-tbody">');
      renderCorrespondenceRows(tbody, data.correspondence_sets, data.languages);
      table.append(tbody);
      container.append(table);
      
      // Click handler for sorting
      container.on('click', '.sortable-header', function(e) {
        e.stopPropagation();
        var col = $(this).data('col');
        var type = $(this).data('type');
        
        // Toggle sort direction
        if (corrSortState.column === col) {
          corrSortState.direction = corrSortState.direction === 'asc' ? 'desc' : 'asc';
        } else {
          corrSortState.column = col;
          corrSortState.direction = 'asc';
        }
        
        // Update sort indicators
        $('.sortable-header .sort-indicator').text('');
        $(this).find('.sort-indicator').text(corrSortState.direction === 'asc' ? ' ▲' : ' ▼');
        
        applyCorrespondenceSortAndFilter();
      });
      
      // Click handler for expanding/collapsing
      container.on('click', '.corr-set-row', function() {
        var idx = $(this).data('idx');
        var icon = $(this).find('.expand-icon');
        var cogContainer = $('.cognate-sets-container[data-idx="' + idx + '"]');
        var cogRow = $(this).next('.cognate-sets-row');
        
        if (cogContainer.hasClass('expanded')) {
          cogContainer.removeClass('expanded');
          cogRow.removeClass('expanded');
          icon.text('▶');
        } else {
          cogContainer.addClass('expanded');
          cogRow.addClass('expanded');
          icon.text('▼');
        }
      });
    }
    
    function renderCorrespondenceRows(tbody, corrSets, languages) {
      tbody.empty();
      
      corrSets.forEach(function(corrSet, idx) {
        // Main row (expandable)
        var row = $('<tr class="corr-set-row" data-idx="' + idx + '">');
        row.append('<td class="expand-icon">▶</td>');
        
        // Pattern cells
        languages.forEach(function(lang) {
          var phoneme = corrSet.pattern[lang] || '-';
          var cell = $('<td class="pattern-cell">');
          if (phoneme === '-' || phoneme === '') {
            cell.addClass('gap-cell').text('-');
          } else {
            cell.text(phoneme);
          }
          row.append(cell);
        });
        
        row.append('<td class="count-cell">' + corrSet.count + '</td>');
        tbody.append(row);
        
        // Expandable cognate sets container
        var cognateSetsRow = $('<tr class="cognate-sets-row">');
        var cognateSetsCell = $('<td colspan="' + (languages.length + 2) + '">');
        var cognateSetsContainer = $('<div class="cognate-sets-container" data-idx="' + idx + '">');
        
        corrSet.cognate_sets.forEach(function(cogSet) {
          cognateSetsContainer.append(renderCognateSet(cogSet, languages, corrSet.pattern));
        });
        
        cognateSetsCell.append(cognateSetsContainer);
        cognateSetsRow.append(cognateSetsCell);
        tbody.append(cognateSetsRow);
      });
    }
    
    function applyCorrespondenceFilters() {
      // Collect filter values
      corrFilters = {};
      $('.corr-filter-input').each(function() {
        var col = $(this).data('col');
        var val = $(this).val().trim();
        if (val) {
          try {
            corrFilters[col] = new RegExp(val);
          } catch (e) {
            // Invalid regex, skip
            corrFilters[col] = null;
          }
        }
      });
      applyCorrespondenceSortAndFilter();
    }
    
    function applyCorrespondenceSortAndFilter() {
      if (!corrData) return;
      
      var languages = corrData.languages;
      var filtered = corrData.correspondence_sets.filter(function(corrSet) {
        // Apply filters
        for (var col in corrFilters) {
          var regex = corrFilters[col];
          if (!regex) continue;
          
          var value;
          if (col === 'count') {
            value = String(corrSet.count);
          } else {
            var lang = languages[parseInt(col)];
            value = corrSet.pattern[lang] || '-';
          }
          
          if (!regex.test(value)) {
            return false;
          }
        }
        return true;
      });
      
      // Apply sorting
      if (corrSortState.column !== null) {
        filtered.sort(function(a, b) {
          var valA, valB;
          
          if (corrSortState.column === 'count') {
            valA = a.count;
            valB = b.count;
          } else {
            var lang = languages[parseInt(corrSortState.column)];
            valA = a.pattern[lang] || '';
            valB = b.pattern[lang] || '';
          }
          
          var cmp;
          if (typeof valA === 'number' && typeof valB === 'number') {
            cmp = valA - valB;
          } else {
            cmp = String(valA).localeCompare(String(valB));
          }
          
          return corrSortState.direction === 'asc' ? cmp : -cmp;
        });
      }
      
      // Re-render rows
      var tbody = $('.corr-tbody');
      renderCorrespondenceRows(tbody, filtered, languages);
    }
    
    function renderCognateSet(cogSet, allLanguages, corrPattern) {
      var div = $('<div class="cognate-set" data-prefid="' + cogSet.prefid + '">');
      
      // Header with protoform and gloss (editable)
      var header = $('<div class="cognate-set-header">');
      header.append('<span class="protoform-label">*</span>');
      
      var protoformInput = $('<input type="text" class="protoform-input">')
        .val(cogSet.proto_form)
        .data('prefid', cogSet.prefid)
        .on('change', function() {
          updateProtoform($(this).data('prefid'), $(this).val(), null);
        })
        .on('click', function(e) {
          e.stopPropagation(); // Prevent row click
        });
      header.append(protoformInput);
      
      header.append('<span class="gloss-label">"</span>');
      var glossInput = $('<input type="text" class="gloss-input">')
        .val(cogSet.proto_gloss)
        .data('prefid', cogSet.prefid)
        .on('change', function() {
          updateProtoform($(this).data('prefid'), null, $(this).val());
        })
        .on('click', function(e) {
          e.stopPropagation(); // Prevent row click
        });
      header.append(glossInput);
      header.append('<span class="gloss-label">"</span>');
      
      div.append(header);
      
      // Alignment table
      if (cogSet.alignment && cogSet.alignment.length > 0) {
        var table = $('<table class="alignment-table">');
        
        // Header row with column numbers
        var headerRow = $('<tr>');
        headerRow.append('<th>Language</th>');
        for (var i = 0; i < cogSet.alignment.length; i++) {
          var th = $('<th>').text(i + 1);
          // Only highlight if this is the pattern column (but don't highlight header)
          headerRow.append(th);
        }
        headerRow.append('<th></th>'); // For remove button
        table.append($('<thead>').append(headerRow));
        
        // Build reflex lookup by language
        var reflexByLang = {};
        if (cogSet.reflexes) {
          cogSet.reflexes.forEach(function(r) {
            reflexByLang[r.lang_name] = r;
          });
        }
        
        // Data rows (one per language)
        var tbody = $('<tbody>');
        cogSet.languages.forEach(function(lang, langIdx) {
          var row = $('<tr>');
          row.append($('<td class="lang-cell">').text(lang));
          
          for (var i = 0; i < cogSet.alignment.length; i++) {
            var phoneme = cogSet.alignment[i][lang] || '';
            var cell = $('<td>');
            
            // Highlight if this is the pattern column AND this cell has a phoneme
            // (not just if the pattern header has a value - the pattern may show '-'
            // when different cognate sets have different values for this language)
            if (i === cogSet.column_index && phoneme !== '') {
              cell.addClass('highlight-col');
            }
            
            if (phoneme === '') {
              cell.addClass('gap-cell').text('-');
            } else {
              cell.text(phoneme);
            }
            row.append(cell);
          }
          
          // Add remove button for daughter languages (not protoform)
          var removeCell = $('<td>');
          if (langIdx > 0 && reflexByLang[lang]) {
            var reflex = reflexByLang[lang];
            var removeBtn = $('<button class="remove-cognate-btn" title="Remove from set">×</button>')
              .data('refid', reflex.refid)
              .data('prefid', cogSet.prefid)
              .on('click', function(e) {
                e.stopPropagation();
                var refid = $(this).data('refid');
                var prefid = $(this).data('prefid');
                if (confirm('Remove this reflex from the cognate set?')) {
                  removeCognateFromSet(refid, prefid, $(this).closest('.cognate-set'));
                }
              });
            removeCell.append(removeBtn);
          }
          row.append(removeCell);
          
          tbody.append(row);
        });
        
        table.append(tbody);
        div.append(table);
      }
      
      return div;
    }
    
    function removeCognateFromSet(refid, prefid, cognateDiv) {
      $.ajax({
        url: '/removesupporting',
        data: {
          refid: refid,
          prefid: prefid
        },
        dataType: 'json',
        success: function() {
          // Remove the row from the table
          cognateDiv.find('tr').each(function() {
            var btn = $(this).find('.remove-cognate-btn');
            if (btn.length && btn.data('refid') === refid) {
              $(this).fadeOut(300, function() { $(this).remove(); });
            }
          });
          console.log('Removed reflex ' + refid + ' from cognate set ' + prefid);
        },
        error: function() {
          alert('Error removing reflex from cognate set');
        }
      });
    }
    
    function updateProtoform(prefid, form, gloss) {
      var data = { refid: prefid };
      if (form !== null) data.form = form;
      if (gloss !== null) data.gloss = gloss;
      
      // Need to get both form and gloss for the update
      if (form === null || gloss === null) {
        // Get the current values from the inputs
        var container = $('.cognate-set[data-prefid="' + prefid + '"]');
        if (form === null) {
          data.form = container.find('.protoform-input').val();
        }
        if (gloss === null) {
          data.gloss = container.find('.gloss-input').val();
        }
      }
      
      $.ajax({
        url: '/updatereflex',
        data: data,
        dataType: 'json',
        success: function() {
          console.log('Protoform updated: ' + prefid);
        },
        error: function() {
          alert('Error updating protoform');
        }
      });
    }
    
    //////////////////////////////////////////
    // Upload Data Dialog
    //////////////////////////////////////////
    
    $('#upload-data-btn').click(function() {
      $.ajax({
        url: '/upload_dialog',
        dataType: 'html',
        success: function(html) {
          $('#dialogs').append(html);
          
          var dialog = $('#upload-data-dialog').dialog({
            title: 'Upload Language Data',
            width: 600,
            height: 550,
            modal: true,
            buttons: [
              {
                text: 'Preview',
                click: previewUpload
              },
              {
                text: 'Upload',
                click: submitUpload,
                disabled: true,
                class: 'upload-submit-btn'
              },
              {
                text: 'Cancel',
                click: function() {
                  $(this).dialog('close');
                }
              }
            ],
            close: function() {
              $(this).dialog('destroy').remove();
            }
          });
          
          // File change triggers preview
          $('#upload-file').on('change', function() {
            // Reset preview
            $('#upload-preview').hide();
            $('#upload-error').hide();
            $('.upload-submit-btn').button('disable');
          });
        }
      });
    });
    
    function previewUpload() {
      var fileInput = $('#upload-file')[0];
      if (!fileInput.files || !fileInput.files[0]) {
        $('#upload-error').text('Please select a file first.').show();
        return;
      }
      
      var formData = new FormData();
      formData.append('file', fileInput.files[0]);
      
      $('#upload-error').hide();
      $('#upload-progress').show();
      $('.progress-text').text('Processing preview...');
      
      $.ajax({
        url: '/preview_upload',
        type: 'POST',
        data: formData,
        processData: false,
        contentType: false,
        success: function(data) {
          $('#upload-progress').hide();
          
          if (data.error) {
            $('#upload-error').text(data.error).show();
            return;
          }
          
          // Populate preview table
          var tbody = $('#preview-table tbody');
          tbody.empty();
          data.preview.forEach(function(entry) {
            var row = $('<tr>');
            row.append($('<td>').text(entry.gloss));
            row.append($('<td>').text(entry.original));
            row.append($('<td>').text(entry.processed));
            tbody.append(row);
          });
          
          $('#preview-stats').text(
            'Total entries: ' + data.total_entries + 
            ' | Format: ' + data.delimiter.toUpperCase()
          );
          $('#upload-preview').show();
          
          // Enable upload button
          $('.upload-submit-btn').button('enable');
        },
        error: function(xhr) {
          $('#upload-progress').hide();
          var msg = 'Error processing file';
          try {
            var resp = JSON.parse(xhr.responseText);
            if (resp.error) msg = resp.error;
          } catch (e) {}
          $('#upload-error').text(msg).show();
        }
      });
    }
    
    function submitUpload() {
      var langname = $('#upload-langname').val().trim();
      if (!langname) {
        $('#upload-error').text('Please enter a language name.').show();
        return;
      }
      
      var fileInput = $('#upload-file')[0];
      if (!fileInput.files || !fileInput.files[0]) {
        $('#upload-error').text('Please select a file.').show();
        return;
      }
      
      var formData = new FormData();
      formData.append('langname', langname);
      formData.append('file', fileInput.files[0]);
      
      // Add selected proto-languages
      $('#upload-protolang option:selected').each(function() {
        formData.append('protolang', $(this).val());
      });
      
      $('#upload-error').hide();
      $('#upload-progress').show();
      $('.progress-fill').css('width', '50%');
      $('.progress-text').text('Uploading...');
      
      $.ajax({
        url: '/upload_data',
        type: 'POST',
        data: formData,
        processData: false,
        contentType: false,
        success: function(data) {
          $('.progress-fill').css('width', '100%');
          
          if (data.error) {
            $('#upload-progress').hide();
            $('#upload-error').text(data.error).show();
            return;
          }
          
          $('.progress-text').text(data.message);
          
          // Reload reflexes table after short delay
          setTimeout(function() {
            reflexes.ajax.reload();
            $('#upload-data-dialog').dialog('close');
          }, 1500);
        },
        error: function(xhr) {
          $('#upload-progress').hide();
          var msg = 'Error uploading data';
          try {
            var resp = JSON.parse(xhr.responseText);
            if (resp.error) msg = resp.error;
          } catch (e) {}
          $('#upload-error').text(msg).show();
        }
      });
    }
    
  });
  