/*global $*/
/*eslint no-undef: "error"*/

$(document).ready(function () {
  console.log('Document ready - comparator.js loaded');
  
  // Track checked rows for reflexes and potcogs (by refid)
  var checkedReflexes = new Set();
  var checkedPotcogs = new Set();
  
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
    reflexes.ajax.reload(null, false);
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
            plangid: plangid
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
            plangid: plangid
          }
        });
      }
    }
  }

  //////////////////////////////////////////
  // Add checked reflexes to cognate sets
  //////////////////////////////////////////

  function addCheckedReflexesToSet() {
    var protoSelection = protoforms.rows({ selected: true }).data();
    if (protoSelection.length === 0) {
      alert('Please select a reconstruction first.');
      return;
    }
    if (checkedReflexes.size === 0) {
      alert('Please check one or more reflexes first (spacebar to toggle).');
      return;
    }
    var refids = Array.from(checkedReflexes);
    for (var i = 0; i < refids.length; i++) {
      for (var j = 0; j < protoSelection.length; j++) {
        var refid = refids[i];
        var prefid = protoSelection[j][0];
        var plangid = protoSelection[j][1];
        console.log('Adding checked ' + refid + ' to ' + prefid + ' in ' + plangid);
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
            plangid: plangid
          }
        });
      }
    }
    // Clear checked reflexes and update checkboxes in the table
    checkedReflexes.clear();
    $('#reflexes tbody .row-checkbox').prop('checked', false);
  }

  //////////////////////////////////////////
  // Add checked potential cognates to cognate sets
  //////////////////////////////////////////

  function addCheckedPotcogsToSet() {
    var protoSelection = protoforms.rows({ selected: true }).data();
    if (protoSelection.length === 0) {
      alert('Please select a reconstruction first.');
      return;
    }
    if (checkedPotcogs.size === 0) {
      alert('Please check one or more potential cognates first (spacebar to toggle).');
      return;
    }
    var refids = Array.from(checkedPotcogs);
    for (var i = 0; i < refids.length; i++) {
      for (var j = 0; j < protoSelection.length; j++) {
        var refid = refids[i];
        var prefid = protoSelection[j][0];
        var plangid = protoSelection[j][1];
        console.log('Adding checked potcog ' + refid + ' to ' + prefid + ' in ' + plangid);
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
            plangid: plangid
          }
        });
      }
    }
    // Clear checked potcogs and update checkboxes in the table
    checkedPotcogs.clear();
    $('#potcogs tbody .row-checkbox').prop('checked', false);
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
    supporting.ajax.reload(null, false);
  }

  //////////////////////////////////////////
  // Edit reflexes
  //////////////////////////////////////////
  
  function editReflexes() {
    var selection = reflexes.rows({
      selected: true
    }).data();
    // Save scroll position before editing
    var scrollBody = $('#reflexes').closest('.dataTables_scrollBody');
    var scrollPos = scrollBody.scrollTop();
    
    for (var i = 0; i < selection.length; i++) {
      $.ajax({
        refid: selection[i][1],
        scrollPos: scrollPos,
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
    var scrollPos = this.scrollPos;
    $('#dialogs').append(data);
    console.log('#edit' + refid + ' reflex');
    $('#edit' + refid).data('refid', refid).data('scrollPos', scrollPos).dialog({
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
    var scrollPos = $(this).data('scrollPos');
    var form = $('#editform' + refid).val();
    var gloss = $('#editgloss' + refid).val();
    var dialogToClose = $(this);
    $.ajax({
      type: 'GET',
      url: '/updatereflex',
      data: {
        refid: refid,
        form: form,
        gloss: gloss
      },
      dataType: 'json',
      success: function() {
        reflexes.ajax.reload(function() {
          // Restore scroll position after reload completes
          var scrollBody = $('#reflexes').closest('.dataTables_scrollBody');
          scrollBody.scrollTop(scrollPos);
        }, false);
        console.log('Update ' + refid + ' ' + form + ' ' + gloss);
        dialogToClose.dialog('close');
      }
    });
  }

  //////////////////////////////////////////
  // Find Potential Cognates (auto-triggered on reflex selection)
  //////////////////////////////////////////

  function findPotCogsForSelection(selection) {
    if (!selection || selection.length === 0) {
      return;
    }
    // Data columns: [0]=langid, [1]=refid, [2]=lname, [3]=ipaform, [4]=gloss, [5]=is_supporting, [6]=form
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
      dataType: 'json',
      success: updatePotCogs,
      error: function(xhr, status, error) {
        console.error('Error finding potential cognates:', error);
      }
    });
  }

  function updatePotCogs() {
    // Reset sort order to similarity (column 6) ascending before reloading
    // Use order() then draw() to ensure the new order is sent to server
    potcogs.order([6, 'asc']).draw();
  }

  //////////////////////////////////////////
  // Find Potential Reconstructions (auto-triggered on reflex selection)
  //////////////////////////////////////////

  function findPotReconsForSelection(selection) {
    if (!selection || selection.length === 0) {
      return;
    }
    // Data columns: [0]=langid, [1]=refid, [2]=lname, [3]=ipaform, [4]=gloss, [5]=is_supporting, [6]=form
    $.ajax({
      url: '/findpotrecons',
      data: {
        ipaform: selection[0][3],  // Use normalized IPA form for similarity
        gloss: selection[0][4],
      },
      dataType: 'json',
      success: function(response) {
        // Switch protoforms table to potrecons mode and reload
        protoformsPotreconsMode = true;
        protoformsRefidsFilter = '';
        // Clear any column filters and filter input values
        protoforms.columns().search('');
        $('#protoforms_wrapper input.column-filter').val('');
        // Reset sort order to column 0 (ID/similarity) ascending
        protoforms.order([0, 'asc']);
        protoforms.ajax.reload(null, false);
      },
      error: function(xhr, status, error) {
        console.error('Error finding potential reconstructions:', error);
      }
    });
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
          reflexes.ajax.reload(null, false);
        }
      });
    });
  }

  ///////////////////////////////////////////////////////////////////////////////
  // Add cognate sets
  ///////////////////////////////////////////////////////////////////////////////

  function newEtymon() {
    console.log('newEtymon called');
    // Fetch dialog HTML from server (just need proto-languages list)
    $.ajax({
      url: '/newetymondialog',
      dataType: 'html',
      success: newEtymonDialog,
      error: function(xhr, status, error) {
        console.error('newEtymon AJAX error:', status, error);
      }
    });
  }

  function newEtymonDialog(data) {
    // Remove any existing dialog first to avoid duplicate IDs
    $('#newset').dialog('destroy').remove();
    $('#dialogs').append(data);
    $('#newset').dialog({
      title: 'New Etymon',
      width: 400,
      buttons: [{
        text: 'Add',
        click: addNewEtymon
      },
      {
        text: 'Cancel',
        click: function() {
          $(this).dialog('close');
        }
      }],
      close: function() {
        $(this).dialog('destroy').remove();
      }
    });
  }

  function addNewEtymon() {
    var protoform = $('#protoform').val();
    var protogloss = $('#protogloss').val();
    var plangid = $('#plangid').val();
    var dialog = $(this);
    
    // Disable dialog buttons to prevent double-submit
    var buttons = dialog.closest('.ui-dialog').find('.ui-dialog-buttonset button');
    buttons.prop('disabled', true);
    
    $.ajax({
      type: 'GET',
      url: '/addnewetymon',
      data: {
        plangid: plangid,
        protoform: protoform,
        protogloss: protogloss
      },
      dataType: 'json',
      success: function(response) {
        if (response.error) {
          alert('Error adding etymon: ' + response.error);
          buttons.prop('disabled', false);
          return;
        }
        if (response.prefid) {
          // Filter Reconstructions to show only the new etymon using server-side filter
          protoformsRefidsFilter = '';
          protoformsPrefidsFilter = response.prefid.toString();
          protoformsPotreconsMode = false;
          protoforms.ajax.reload(null, false);
          // Find potential reflexes for this new etymon (use ipaform from server response)
          var ipaform = response.ipaform || protoform;
          findPotReflexesForEtymon(response.prefid, plangid, ipaform, protogloss);
        }
        dialog.dialog('close');
      },
      error: function(xhr, status, error) {
        var msg = 'Error adding etymon';
        try {
          var resp = JSON.parse(xhr.responseText);
          if (resp.error) msg = resp.error;
        } catch (e) {}
        alert(msg);
        buttons.prop('disabled', false);
      }
    });
  }

  function findPotReflexesForSelection(selection) {
    if (!selection || selection.length === 0) {
      return;
    }
    // Data columns: [0]=refid, [1]=plangid, [2]=lname, [3]=ipaform, [4]=gloss
    var prefid = selection[0][0];
    var plangid = selection[0][1];
    var ipaform = selection[0][3];
    var gloss = selection[0][4];
    findPotReflexesForEtymon(prefid, plangid, ipaform, gloss);
  }

  function findPotReflexesForEtymon(prefid, plangid, ipaform, gloss) {
    $.ajax({
      url: '/findpotreflexes',
      data: {
        prefid: prefid,
        plangid: plangid,
        ipaform: ipaform,
        gloss: gloss
      },
      dataType: 'json',
      success: function(response) {
        // Reset sort order to similarity and reload potcogs table
        // Use order() then draw() to ensure the new order is sent to server
        potcogs.order([6, 'asc']).draw();
      },
      error: function(xhr, status, error) {
        console.error('Error finding potential reflexes:', error);
      }
    });
  }

  //////////////////////////////////////////
  // Edit protoforms
  //////////////////////////////////////////

  function editProtoform() {
    console.log('editProtoform called');
    var selection = protoforms.rows({
      selected: true
    }).data();
    // Save scroll position before editing
    var scrollBody = $('#protoforms').closest('.dataTables_scrollBody');
    var scrollPos = scrollBody.scrollTop();
    
    for (var i = 0; i < selection.length; i++) {
      $.ajax({
        refid: selection[i][0],
        scrollPos: scrollPos,
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
    var scrollPos = this.scrollPos;
    $('#dialogs').append(data);
    $('#edit' + refid).data('refid', refid).data('scrollPos', scrollPos).dialog({
      title: 'Edit Protoform',
      buttons: [{
        text: 'Update',
        click: function() {
          var dlgRefid = $(this).data('refid');
          var dlgScrollPos = $(this).data('scrollPos');
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
              protoforms.ajax.reload(function() {
                // Restore scroll position after reload completes
                var scrollBody = $('#protoforms').closest('.dataTables_scrollBody');
                scrollBody.scrollTop(dlgScrollPos);
              }, false);
              supporting.ajax.reload(null, false);
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
    console.log('editMorphOfSupportingForm called');
    var protoSelection = protoforms.rows({
      selected: true
    }).data();
    var supSelection = supporting.rows({
      selected: true
    }).data();
    
    console.log('protoSelection length: ' + protoSelection.length);
    console.log('supSelection length: ' + supSelection.length);
    
    if (protoSelection.length === 0) {
      alert('Please select a protoform first.');
      return;
    }
    if (supSelection.length === 0) {
      alert('Please select a supporting form to edit.');
      return;
    }
    
    var prefid = protoSelection[0][0];
    var plangid = protoSelection[0][1];
    for (var i = 0; i < supSelection.length; i++) {
      var refid = supSelection[i][0];
      var morph_index = supSelection[i][4];
      console.log('Editing refid=' + refid + ' of prefid=' + prefid + ' in plangid=' + plangid);
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
    
    // Get morph_index from the selected morph in the rendered template
    var selectedMorph = morphsContainer.find('.selected-morph');
    var morph_index = selectedMorph.length ? parseInt(selectedMorph.data('index')) : 0;
    dialog.data('morph_index', morph_index);
    
    // Setup morph click handlers
    function setupMorphClickHandlers() {
      var morphs = morphsContainer.find('.morph-span');
      morphs.off('click').on('click', function() {
        var clickedIndex = parseInt($(this).data('index'));
        morphs.removeClass('selected-morph');
        $(this).addClass('selected-morph');
        dialog.data('morph_index', clickedIndex);
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
          supporting.ajax.reload(null, false);
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
      $.ajax({
        url: '/updatemorph',
        data: {
          refid: params.refid,
          prefid: params.prefid,
          morph_index: params.dialog.data('morph_index')
        },
        success: function() {
          params.dialog.dialog('close');
          supporting.ajax.reload(null, false);
        }
      })
    }
  }

  //////////////////////////////////////////
  // Delete protoforms
  //////////////////////////////////////////

  function deleteProtoform() {
    console.log('deleteProtoform called');
    var selectedRows = protoforms.rows({ selected: true });
    var selectedData = selectedRows.data();
    
    if (selectedData.length === 0) {
      alert('Please select a reconstruction to delete.');
      return;
    }
    
    var prefid = selectedData[0][0];
    var form = selectedData[0][3] || '';
    var gloss = selectedData[0][4] || '';
    
    if (!confirm('Delete reconstruction "' + form + '" (' + gloss + ')?')) {
      return;
    }
    
    console.log('Deleting prefid:' + prefid);
    $.ajax({
      url: '/deleteprotoform',
      data: {
        prefid: prefid
      },
      success: function() {
        console.log('Deleted protoform');
        protoforms.ajax.reload(null, false);
        supporting.ajax.reload(null, false);
      },
      error: function(xhr, status, error) {
        console.log('Error deleting protoform: ' + error);
        alert('Error deleting reconstruction: ' + error);
      }
    });
  }

  ////////////////////////////////////////
  // Data tables
  ////////////////////////////////////////

  // Store refids filter for protoforms table (empty = show all)
  var protoformsRefidsFilter = '';
  // Store prefids filter for protoforms table (direct protoform ID filter)
  var protoformsPrefidsFilter = '';
  // Store potrecons mode for protoforms table (false = normal, true = show potential reconstructions)
  var protoformsPotreconsMode = false;

  console.log('Initializing protoforms table...');
  var protoforms = $('#protoforms').DataTable({
    dom: 'Brtip',
    select: {
      style: 'single'
    },
    scrollY: '100px',  // Initial value, will be recalculated
    scrollCollapse: false,
    paging: true,
    pageLength: 200,
    deferRender: true,
    orderCellsTop: true,  // Sort by clicking header row, not filter row
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
        d.prefids = protoformsPrefidsFilter;
        d.potrecons = protoformsPotreconsMode;
      }
    },
    buttons: [
      {
        text: 'New Etymon',
        action: function(e, dt, node, config) {
          console.log('New Etymon button clicked');
          newEtymon();
        }
      },
      {
        text: 'Edit',
        action: function(e, dt, node, config) {
          console.log('Edit button clicked');
          editProtoform();
        }
      },
      {
        text: 'Delete',
        action: function(e, dt, node, config) {
          console.log('Delete button clicked');
          deleteProtoform();
        }
      },
      {
        text: 'Show All',
        action: function(e, dt, node, config) {
          console.log('Show All button clicked');
          protoformsRefidsFilter = '';
          protoformsPrefidsFilter = '';
          protoformsPotreconsMode = false;
          protoforms.ajax.reload(null, false);
        }
      }
    ]
  });
  console.log('Protoforms table initialized:', protoforms);

  var reflexes = $('#reflexes').DataTable({
      dom: 'Brtip',
      select: {
        style: 'single'
      },
      serverSide: true,
      scrollY: '100px',  // Initial value, will be recalculated
      scrollCollapse: false,
      paging: true,
      pageLength: 200,
      deferRender: true,
      orderCellsTop: true,  // Sort by clicking header row, not filter row
      ajax: {
        url: "/reflexes",
        type: "GET"
      },
      buttons: [
        {
          text: 'Add Checked to Set',
          action: addCheckedReflexesToSet
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
          text: 'Protoforms',
          action: function() {
            // Get checked reflex ids and filter protoforms table
            if (checkedReflexes.size === 0) {
              alert('Please check one or more reflexes first (spacebar to toggle).');
              return;
            }
            var refids = Array.from(checkedReflexes);
            protoformsRefidsFilter = refids.join(',');
            protoformsPotreconsMode = false;
            protoforms.ajax.reload(null, false);
          }
        },
        {
          text: 'Clear Checks',
          action: function() {
            checkedReflexes.clear();
            reflexes.rows().invalidate().draw(false);
          }
        }
      ],
      // Server returns: [langid, refid, lname, ipaform, gloss, is_supporting, form]
      // Table has 8 columns: [checkbox, langid, refid, lname, ipaform, gloss, is_supporting, form]
      columns: [
        {
          data: null,
          orderable: false,
          className: 'checkbox-column',
          render: function(data, type, row, meta) {
            // row[1] is refid
            var refid = row[1];
            var checked = checkedReflexes.has(refid) ? 'checked' : '';
            return '<input type="checkbox" class="row-checkbox" data-refid="' + refid + '" ' + checked + '>';
          }
        },
        { data: 0, visible: false },  // langid
        { data: 1, visible: false },  // refid
        { data: 2 },                   // lname (Language)
        { data: 3 },                   // ipaform (Form)
        { data: 4 },                   // gloss
        { data: 5, visible: false },  // is_supporting (InSet)
        { data: 6, visible: false }   // form (Form orig)
      ],
      createdRow: function(row, data, dataIndex) {
        // data[5] is is_supporting (1 if in cognate set, 0 otherwise)
        if (data[5] === 1) {
          $(row).css('font-weight', 'bold');
        }
      }
    });
    
    // Handle checkbox clicks in reflexes table
    $('#reflexes tbody').on('click', '.row-checkbox', function(e) {
      e.stopPropagation();  // Don't trigger default row selection behavior
      var refid = parseInt($(this).data('refid'));
      if (this.checked) {
        checkedReflexes.add(refid);
      } else {
        checkedReflexes.delete(refid);
      }
      // Select the row that contains this checkbox
      var row = $(this).closest('tr');
      reflexes.rows().deselect();  // Deselect all rows first (single selection mode)
      reflexes.row(row).select();  // Select this row
    });
    
    var potcogs = $('#potcogs').DataTable({
      dom: 'Brtip',
      select: {
        style: 'single'
      },
      serverSide: true,
      scrollY: '100px',  // Initial value, will be recalculated
      scrollCollapse: false,
      paging: true,
      pageLength: 200,
      deferRender: true,
      orderCellsTop: true,  // Sort by clicking header row, not filter row
      order: [[6, 'asc']],  // Order by sim (column 6) ascending (lowest distance = best match)
      ajax: {
        url: "/potcogs",
        type: "GET"
      },
      buttons: [
        {
          text: "Add Checked to Set",
          action: addCheckedPotcogsToSet
        },
        {
          text: 'Clear Checks',
          action: function() {
            checkedPotcogs.clear();
            potcogs.rows().invalidate().draw(false);
          }
        }
      ],
      // Server returns: [langid, refid, lname, ipaform, gloss, sim]
      // Table has 7 columns: [checkbox, langid, refid, lname, ipaform, gloss, sim]
      columns: [
        {
          data: null,
          orderable: false,
          className: 'checkbox-column',
          render: function(data, type, row, meta) {
            // row[1] is refid
            var refid = row[1];
            var checked = checkedPotcogs.has(refid) ? 'checked' : '';
            return '<input type="checkbox" class="row-checkbox" data-refid="' + refid + '" ' + checked + '>';
          }
        },
        { data: 0, visible: false },  // langid
        { data: 1, visible: false },  // refid
        { data: 2 },                   // lname (Language)
        { data: 3 },                   // ipaform (Form)
        { data: 4 },                   // gloss
        { data: 5, visible: false }   // sim
      ]
    });
    
    // Handle checkbox clicks in potcogs table
    $('#potcogs tbody').on('click', '.row-checkbox', function(e) {
      e.stopPropagation();  // Don't trigger default row selection behavior
      var refid = parseInt($(this).data('refid'));
      if (this.checked) {
        checkedPotcogs.add(refid);
      } else {
        checkedPotcogs.delete(refid);
      }
      // Select the row that contains this checkbox
      var row = $(this).closest('tr');
      potcogs.rows().deselect();  // Deselect all rows first (single selection mode)
      potcogs.row(row).select();  // Select this row
    });
    
    var supporting = $('#supporting').DataTable({
      dom: 'Brtip',
      select: {
        style: 'single'
      },
      serverSide: true,
      scrollY: '100px',  // Initial value, will be recalculated
      scrollCollapse: false,
      paging: true,
      pageLength: 200,
      deferRender: true,
      orderCellsTop: true,  // Sort by clicking header row, not filter row
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
    
    // Prevent clicks on filter inputs from triggering column sorting
    $(document).on('click', '.column-filter', function(e) {
      e.stopPropagation();
    });
    
    //////////////////////////////////////////
    // Initial table focus and selection
    //////////////////////////////////////////
    
    // Select first row in each table after initial data load
    function selectFirstRowOnLoad(table) {
      table.one('draw', function() {
        var allRows = table.rows().indexes().toArray();
        if (allRows.length > 0 && table.rows({ selected: true }).indexes().toArray().length === 0) {
          table.row(allRows[0]).select();
        }
      });
    }
    
    // Set up initial selection for all tables
    selectFirstRowOnLoad(reflexes);
    selectFirstRowOnLoad(protoforms);
    selectFirstRowOnLoad(potcogs);
    selectFirstRowOnLoad(supporting);
    
    //////////////////////////////////////////
    // Auto-trigger potential cognates/reflexes on selection
    //////////////////////////////////////////
    
    // When a reflex is selected, automatically find potential cognates AND potential reconstructions
    reflexes.on('select', function(e, dt, type, indexes) {
      var selection = reflexes.rows(indexes).data().toArray();
      findPotCogsForSelection(selection);
      findPotReconsForSelection(selection);
    });
    
    // When a protoform/reconstruction is selected, automatically find potential reflexes
    protoforms.on('select', function(e, dt, type, indexes) {
      var selection = protoforms.rows(indexes).data().toArray();
      var prefid = selection[0][0];
      $('#protoforms').data('prefid', prefid);
      supporting.draw();
      // Auto-trigger potential reflexes
      findPotReflexesForSelection(selection);
    });
    
    //////////////////////////////////////////
    // Keyboard Shortcuts
    //////////////////////////////////////////
    
    // Track which table is currently focused
    var focusedTable = null;
    var tableMap = {
      'L': { table: reflexes, id: 'reflexes', name: 'Reflexes (Lexicon)' },
      'R': { table: protoforms, id: 'protoforms', name: 'Reconstructions' },
      'P': { table: potcogs, id: 'potcogs', name: 'Potential Cognates' },
      'S': { table: supporting, id: 'supporting', name: 'Supporting Forms' }
    };
    
    // Visual indicator for focused table
    function setFocusedTable(tableKey) {
      // Remove focus indicator from all tables
      $('.table-container').removeClass('table-focused');
      
      if (tableKey && tableMap[tableKey]) {
        focusedTable = tableMap[tableKey];
        $('#' + focusedTable.id).closest('.table-container').addClass('table-focused');
        
        // If no row is selected, select the first row
        var selectedRows = focusedTable.table.rows({ selected: true }).indexes().toArray();
        if (selectedRows.length === 0) {
          var allRows = focusedTable.table.rows().indexes().toArray();
          if (allRows.length > 0) {
            focusedTable.table.row(allRows[0]).select();
          }
        }
      }
    }
    
    // Select next/previous row in focused table
    function selectAdjacentRow(direction) {
      if (!focusedTable) {
        alert('Press L, R, P, or S to focus a table first.');
        return;
      }
      
      var table = focusedTable.table;
      var tableId = focusedTable.id;
      
      // Get all visible rows (tbody tr elements)
      var $rows = $('#' + tableId + ' tbody tr');
      var rowCount = $rows.length;
      
      if (rowCount === 0) return;
      
      // Find currently selected row by looking for the 'selected' class
      var currentIndex = -1;
      $rows.each(function(idx) {
        if ($(this).hasClass('selected')) {
          currentIndex = idx;
          return false; // break
        }
      });
      
      var newIndex;
      if (currentIndex === -1) {
        // No selection, select first or last row depending on direction
        newIndex = direction === 1 ? 0 : rowCount - 1;
      } else {
        newIndex = currentIndex + direction;
        // Bounds check
        if (newIndex < 0) newIndex = 0;
        if (newIndex >= rowCount) newIndex = rowCount - 1;
      }
      
      // Deselect all rows and select the new one using DataTables API
      table.rows().deselect();
      table.row($rows[newIndex]).select();
      
      // Scroll to make the selected row visible
      $rows[newIndex].scrollIntoView({ block: 'nearest', behavior: 'smooth' });
    }
    
    // Edit dialog for currently selected item
    function editSelectedItem() {
      if (!focusedTable) {
        alert('Press L, R, P, or S to focus a table first.');
        return;
      }
      
      var table = focusedTable.table;
      var selection = table.rows({ selected: true }).data();
      
      if (selection.length === 0) {
        alert('Please select an item first.');
        return;
      }
      
      // Trigger the appropriate edit function based on focused table
      if (focusedTable.id === 'reflexes') {
        editReflexes();
      } else if (focusedTable.id === 'protoforms') {
        editProtoform();
      } else if (focusedTable.id === 'supporting') {
        editMorphOfSupportingForm();
      } else if (focusedTable.id === 'potcogs') {
        // Potcogs doesn't have an edit function, could add item to set instead
        alert('Use "A" to add potential cognates to a set.');
      }
    }
    
    // Toggle checkbox on selected row in reflexes or potcogs
    function toggleSelectedCheckbox() {
      if (!focusedTable) return;
      
      if (focusedTable.id === 'reflexes') {
        var selectedRowIndexes = reflexes.rows({ selected: true }).indexes().toArray();
        var selectedRows = reflexes.rows({ selected: true }).data().toArray();
        if (selectedRows.length > 0) {
          var refid = selectedRows[0][1];  // refid is at index 1
          if (checkedReflexes.has(refid)) {
            checkedReflexes.delete(refid);
          } else {
            checkedReflexes.add(refid);
          }
          // Update just the checkbox in the row without full invalidate/draw
          var checkbox = reflexes.row(selectedRowIndexes[0]).node().querySelector('.row-checkbox');
          if (checkbox) {
            checkbox.checked = checkedReflexes.has(refid);
          }
        }
      } else if (focusedTable.id === 'potcogs') {
        var selectedRowIndexes = potcogs.rows({ selected: true }).indexes().toArray();
        var selectedRows = potcogs.rows({ selected: true }).data().toArray();
        if (selectedRows.length > 0) {
          var refid = selectedRows[0][1];  // refid is at index 1
          if (checkedPotcogs.has(refid)) {
            checkedPotcogs.delete(refid);
          } else {
            checkedPotcogs.add(refid);
          }
          // Update just the checkbox in the row without full invalidate/draw
          var checkbox = potcogs.row(selectedRowIndexes[0]).node().querySelector('.row-checkbox');
          if (checkbox) {
            checkbox.checked = checkedPotcogs.has(refid);
          }
        }
      }
    }
    
    // Add checked items to reconstruction/etymon (A key)
    function addCheckedToSet() {
      // Check if a reconstruction is selected
      var protoSelection = protoforms.rows({ selected: true }).data();
      if (protoSelection.length === 0) {
        alert('Please select a reconstruction/etymon first (focus Reconstructions with R and select one).');
        return;
      }
      
      // Add all checked reflexes and potcogs
      var hasChecked = checkedReflexes.size > 0 || checkedPotcogs.size > 0;
      if (!hasChecked) {
        alert('Please check one or more items first (spacebar to toggle checkbox on selected row).');
        return;
      }
      
      if (checkedReflexes.size > 0) {
        addCheckedReflexesToSet();
      }
      if (checkedPotcogs.size > 0) {
        addCheckedPotcogsToSet();
      }
      
      // Return focus to Reflexes pane after adding
      setFocusedTable('L');
    }
    
    // Global keyboard handler
    $(document).on('keydown', function(e) {
      // Ignore if typing in an input field or focused on dialog elements
      if ($(e.target).is('input, textarea, select')) {
        return;
      }
      // Ignore if focus is inside a dialog (but not on the main page tables)
      if ($(e.target).closest('.ui-dialog').length && !$(e.target).closest('.table-container').length) {
        return;
      }
      
      // Ignore if any modifier key is pressed (Ctrl, Alt, Meta/Command)
      if (e.ctrlKey || e.altKey || e.metaKey) {
        return;
      }
      
      var key = e.key.toUpperCase();
      
      // Table focus shortcuts: L, R, P, S
      if (tableMap[key]) {
        e.preventDefault();
        setFocusedTable(key);
        return;
      }
      
      // Navigation shortcuts: > and < (or . and ,) or Arrow keys
      if (e.key === '>' || e.key === '.' || e.key === 'ArrowDown') {
        e.preventDefault();
        selectAdjacentRow(1);  // Next row
        return;
      }
      if (e.key === '<' || e.key === ',' || e.key === 'ArrowUp') {
        e.preventDefault();
        selectAdjacentRow(-1);  // Previous row
        return;
      }
      
      // Spacebar: toggle checkbox on selected row (reflexes or potcogs only)
      if (e.key === ' ') {
        e.preventDefault();
        toggleSelectedCheckbox();
        return;
      }
      
      // Edit shortcut: E
      if (key === 'E') {
        e.preventDefault();
        editSelectedItem();
        return;
      }
      
      // Add to set shortcut: A - adds all checked items from reflexes and potcogs
      if (key === 'A') {
        e.preventDefault();
        addCheckedToSet();
        return;
      }
    });
    
    // Focus Reflexes table initially (after a short delay to ensure rendering)
    setTimeout(function() {
      setFocusedTable('L');
    }, 500);
    
    //////////////////////////////////////////
    // Correspondence Sets Dialog
    //////////////////////////////////////////
    
    $('#correspondence-sets-btn').click(function() {
      // Remove any existing dialog first to prevent duplicates
      var existingDialog = $('#correspondence-sets-dialog');
      if (existingDialog.length) {
        if (existingDialog.hasClass('ui-dialog-content')) {
          existingDialog.dialog('destroy');
        }
        existingDialog.remove();
      }
      
      $.ajax({
        url: '/correspondence_sets_dialog',
        dataType: 'html',
        success: function(html) {
          $('#dialogs').append(html);
          
          // Get reference to dialog before it's moved by jQuery UI
          var dialog = $('#correspondence-sets-dialog');
          var select = dialog.find('#protolang-select');
          
          // Load proto-languages dropdown
          $.ajax({
            url: '/protolanguages',
            dataType: 'json',
            success: function(data) {
              data.forEach(function(lang) {
                select.append($('<option>', {
                  value: lang.langid,
                  text: lang.name
                }));
              });
            }
          });
          
          // Create dialog
          dialog.dialog({
            title: 'Correspondence Sets',
            width: 900,
            height: 650,
            modal: false,
            close: function() {
              $(this).dialog('destroy').remove();
            }
          });
          
          // Load button handler - use scoped selector
          dialog.find('#load-corr-sets-btn').click(function() {
            var plangid = select.val();
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
          })
          .on('click mousedown', function(e) {
            e.stopPropagation(); // Prevent sorting when clicking in filter
          });
        td.append(input);
        filterRow.append(td);
      });
      // Count filter
      var countTd = $('<td>');
      var countInput = $('<input type="text" class="corr-filter-input" data-col="count" placeholder="regex">')
        .on('input', function() {
          applyCorrespondenceFilters();
        })
        .on('click mousedown', function(e) {
          e.stopPropagation(); // Prevent sorting when clicking in filter
        });
      countTd.append(countInput);
      filterRow.append(countTd);
      thead.append(filterRow);
      
      table.append(thead);
      
      var tbody = $('<tbody class="corr-tbody">');
      renderCorrespondenceRows(tbody, data.correspondence_sets, data.languages);
      table.append(tbody);
      container.append(table);
      
      // Unbind previous handlers to prevent duplicates, then rebind
      container.off('click', '.sortable-header');
      container.off('click', '.corr-set-row');
      
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
        
        // Languages that have data in this correspondence set
        var langsWithData = corrSet.languages_with_data || [];
        
        // Pattern cells
        languages.forEach(function(lang, langIdx) {
          var phoneme = corrSet.pattern[lang] || '';
          var cell = $('<td class="pattern-cell">');
          var hasData = langsWithData.indexOf(lang) !== -1;
          
          if (phoneme === '-' || phoneme === '') {
            if (hasData) {
              // Language has data but gap in this correspondence - show empty set symbol
              cell.addClass('gap-cell').text('∅');
            } else {
              // No data from this language at all - show em-dash and gray out
              cell.addClass('no-data-cell').text('—');
            }
          } else {
            cell.text(phoneme);
            // Store data for double-click lookup
            cell.data('lang', lang);
            cell.data('phoneme', phoneme);
            cell.addClass('phoneme-clickable');
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
      
      // Add double-click handler for phoneme cells
      tbody.find('.phoneme-clickable').off('dblclick').on('dblclick', function(e) {
        e.stopPropagation();
        var lang = $(this).data('lang');
        var phoneme = $(this).data('phoneme');
        if (lang && phoneme) {
          showPhonemeDialog(lang, phoneme);
        }
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
        .on('change', function(e) {
          e.stopPropagation();
          updateProtoform($(this).data('prefid'), $(this).val(), null);
        })
        .on('click mousedown focus keydown keyup', function(e) {
          e.stopPropagation(); // Prevent event bubbling to row
        });
      header.append(protoformInput);
      
      header.append('<span class="gloss-label">"</span>');
      var glossInput = $('<input type="text" class="gloss-input">')
        .val(cogSet.proto_gloss)
        .data('prefid', cogSet.prefid)
        .on('change', function(e) {
          e.stopPropagation();
          updateProtoform($(this).data('prefid'), null, $(this).val());
        })
        .on('click mousedown focus keydown keyup', function(e) {
          e.stopPropagation(); // Prevent event bubbling to row
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
    
    // Show dialog with all cognate sets containing a specific phoneme for a language
    function showPhonemeDialog(language, phoneme) {
      // Get the current proto-language ID from the select
      var plangid = $('#protolang-select').val();
      if (!plangid) {
        alert('Please select a proto-language first');
        return;
      }
      
      // Fetch cognate sets for this language/phoneme combination
      $.ajax({
        url: '/cognates_by_phoneme',
        data: {
          plangid: plangid,
          language: language,
          phoneme: phoneme
        },
        dataType: 'json',
        success: function(data) {
          if (data.error) {
            alert(data.error);
            return;
          }
          renderPhonemeDialog(data, language, phoneme);
        },
        error: function() {
          alert('Error fetching cognate sets for phoneme');
        }
      });
    }
    
    function renderPhonemeDialog(data, language, phoneme) {
      // Remove any existing phoneme dialog
      $('#phoneme-lookup-dialog').remove();
      
      var dialogHtml = '<div id="phoneme-lookup-dialog">' +
        '<div class="phoneme-dialog-header">' +
        '<strong>' + language + '</strong> /' + phoneme + '/ — ' + 
        data.cognate_sets.length + ' cognate set(s)' +
        '</div>' +
        '<div class="phoneme-dialog-content"></div>' +
        '</div>';
      
      $('#dialogs').append(dialogHtml);
      
      var content = $('#phoneme-lookup-dialog .phoneme-dialog-content');
      
      if (data.cognate_sets.length === 0) {
        content.html('<p>No cognate sets found.</p>');
      } else {
        // Render each cognate set
        data.cognate_sets.forEach(function(cogSet) {
          // Create pattern from alignment column
          var pattern = {};
          if (cogSet.alignment && cogSet.column_index < cogSet.alignment.length) {
            pattern = cogSet.alignment[cogSet.column_index];
          }
          content.append(renderCognateSet(cogSet, data.languages, pattern));
        });
      }
      
      $('#phoneme-lookup-dialog').dialog({
        title: 'Cognate Sets with ' + language + ' /' + phoneme + '/',
        width: Math.min(900, $(window).width() - 100),
        height: Math.min(600, $(window).height() - 100),
        modal: false,
        position: { my: 'center', at: 'center', of: window },
        close: function() {
          $(this).dialog('destroy').remove();
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
            reflexes.ajax.reload(null, false);
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
    
    ////////////////////////////////////////
    // Resize tables to fill available space
    ////////////////////////////////////////
    
    function resizeTables() {
      $('.table-container').each(function() {
        var container = $(this);
        var wrapper = container.find('.dataTables_scrollBody');
        if (wrapper.length === 0) return;
        
        // Calculate available height: container height minus header, buttons, scrollHead, info bar
        var containerHeight = container.height();
        var headerHeight = container.find('h3').outerHeight() || 0;
        var buttonsHeight = container.find('.dt-buttons').outerHeight() || 0;
        var scrollHeadHeight = container.find('.dataTables_scrollHead').outerHeight() || 0;
        var infoHeight = container.find('.dataTables_info').outerHeight() || 0;
        var paginateHeight = container.find('.dataTables_paginate').outerHeight() || 0;
        var padding = 24;  // Padding from table-wrapper
        
        var availableHeight = containerHeight - headerHeight - buttonsHeight - scrollHeadHeight - infoHeight - paginateHeight - padding;
        
        if (availableHeight > 100) {
          wrapper.css('max-height', availableHeight + 'px');
          wrapper.css('height', availableHeight + 'px');
        }
      });
    }
    
    // Resize on load and window resize
    $(window).on('resize', function() {
      resizeTables();
    });
    
    // Initial resize after a short delay to ensure DataTables are fully rendered
    setTimeout(resizeTables, 100);
    
  });
  