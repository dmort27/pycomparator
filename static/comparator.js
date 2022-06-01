/*global $*/
/*eslint no-undef: "error"*/

$(document).ready(function () {
  
  //////////////////////////////////////////
  // Add reflexes to master list
  //////////////////////////////////////////
  
  
  // Totally wrong
  
  // function newReflex() {
  //   console.log('Adding reflex');
  //   $.ajax({
  //     url: '/newreflexdialog',
  //     data: {},
  //     dataType: 'html',
  //     success: newReflexDialog
  //   })
  // }
  
  // function newReflexDialog() {
  //   console.log("Add reflex");
  //   $.ajax({
  //     url: '/newreflexdialog',
  //     data: {},
  //     dataType: 'html',
  //     success: addNewReflex
  //   });
  //   $('#newreflex').dialog({
  //     title: 'Add Reflex',
  //     buttons: [{
  //       text: 'Add',
  //       click: addNewReflex
  //     },
  //     {
  //       text: 'Cancel',
  //       click: function() {
  //         console.log('Cancel');
  //         $(this).dialog('close');
  //       }
  //     }]
  //   })
  // }
  
  // function addNewReflex() {
  //   var langid = $('#langname').val();
  //   var form = $('#form').val();
  //   var gloss = $('#gloss').val();
  //   var sourceid = $('#sourceid').val();
  //   $.ajax({
  //     type: 'GET',
  //     url: '/addnewreflex',
  //     data: {
  //       langid: langid,
  //       sourceid: sourceid,
  //       form: form,
  //       gloss: gloss
  //     },
  //     dataType: 'json'
  //   });
  //   reflexes.ajax.reload();
  //   $(this).dialog.close();
  // }
  
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
        var refid = refSelection[i][0];
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
  
  // function removeReflexFromSupportingForms() {
  //   console.log('Remove reflex');
  // }
  
  //////////////////////////////////////////
  // Edit reflexes
  //////////////////////////////////////////
  
  function editReflexes() {
    var selection = reflexes.rows({
      selected: true
    }).data();
    for (var i = 0; i < selection.length; i++) {
      $.ajax({
        refid: selection[i][0],
        url: '/reflexdialog',
        data: {
          refid: selection[i][0],
          lname: selection[i][1],
          form: selection[i][2],
          gloss: selection[i][3],
        },
        dataType: 'html',
        success: editReflexDialog
      });
    }
  }
  
  function editReflexDialog(data) {
    var refid = this.refid;
    $('#dialogs').append(data);
    console.log('#edit' + refid);
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
        lname: selection[i][1],
        form: selection[i][2],
        gloss: selection[i][3],
      },
      dataType: 'html',
      success: editProtoformDialog
    });
  }
}

function editProtoformDialog(data) {
  var refid = this.refid;
  $('#dialogs').append(data);
  console.log('#edit' + refid);
  $('#edit' + refid).data('refid', refid).dialog({
    title: 'Edit Protoform',
    buttons: [{
      text: 'Update',
      click: updateProtoform
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

function updateProtoform() {
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
  protoforms.ajax.reload();
  console.log('Update ' + refid + ' ' + form + ' ' + gloss);
  $(this).dialog('close');
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
  var dialog = $('#supporting' + this.refid)
  var morphs = $('#supporting' + this.refid + ' > span');
  dialog.data('morph_index', this.morph_index);
  morphs
  .eq(this.morph_index)
  .addClass('selected-morph');
  morphs.each(
    function(i) {
      $(this).click(
        function() {
          morphs.removeClass('selected-morph');
          $(this).addClass('selected-morph');
          dialog.data('morph_index', i);
          console.log('morph_index in click: ' + dialog.data('morph_index'));
        }
        )
      }
      );
      dialog
      .dialog({
        title: 'Select Morph',
        buttons: [{
          text: 'OK',
          click: updateMorphSelection({
            refid: this.refid,
            prefid: this.prefid,
            plangid: this.plangid,
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
          }
        });
      });
    }
    
    ////////////////////////////////////////
    // Data tables
    ////////////////////////////////////////
    
    var protoforms = $('#protoforms').DataTable({
      dom: 'Blrtp',
      select: {
        style: 'single'
      },
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
        type: "GET"
      },
      buttons: [
        {
          text: 'Edit',
          action: editProtoform
        },
        {
          text: 'Delete',
          action: deleteProtoform
        }
      ]
    });
    
    var reflexes = $('#reflexes').DataTable({
      dom: 'Blrtp',
      lengthMenu: [20, 40, 60],
      select: true,
      serverSide: true,
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
        }
      ],
      columnDefs: [{
        targets: [0],
        visible: false,
      }]
    });
    
    var supporting = $('#supporting').DataTable({
      dom: 'Blrtp',
      select: true,
      serverSide: true,
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
          text: 'Remove from Set'
        }
      ]
    });
    
    ////////////////////////////////////////
    // Search bars
    ////////////////////////////////////////
    
    $('#reflexes tfoot th').each(function() {
      var title = $(this).text();
      $(this).html('<input type="text" placeholder="Search ' + title + '" />');
    });
    
    $('#protoforms tfoot th').each(function() {
      var title = $(this).text();
      $(this).html('<input type="text" placeholder="Search ' + title + '" />');
    });
    
    reflexes.columns().eq(0).each(function(colIdx) {
      $('input', reflexes.column(colIdx).footer()).on('keyup change', function() {
        reflexes
        .column(colIdx)
        .search(this.value)
        .draw();
      });
    });
    
    protoforms.columns().eq(0).each(function(colIdx) {
      $('input', protoforms.column(colIdx).footer()).on('keyup change', function() {
        protoforms
        .column(colIdx)
        .search(this.value)
        .draw();
      });
    });
    
    protoforms.on('select', function(e, dt, type, indexes) {
      var prefid = protoforms.rows(indexes).data().toArray()[0][0];
      $('#protoforms').data('prefid', prefid);
      supporting.draw();
    });
    
  });
  