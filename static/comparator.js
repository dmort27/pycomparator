window.prefid = 0;

$(document).ready(function() {

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
        refid = refSelection[i][0]
        prefid = protoSelection[j][0]
        console.log('Adding ' + refid + ' to ' + prefid)
        $.ajax(
          {
            url: '/addsupporting',
            data: {
              refid: refid,
              prefid: prefid
            },
            dataType: 'json',
            success: reloadSupporingForms
          }
        )
      }
    }
  };

  function reloadSupporingForms() {
    supporting.reload();
  }

  function editReflexes() {
    var selection = reflexes.rows({
      selected: true
    }).data();
    var records = [];
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

  function editProtoform() {
    var selection = protoforms.rows({
      selected: true
    }).data();
    var records = [];
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

  function updateReflex() {
    refid = $(this).data('refid');
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

  function updateProtoform() {
    refid = $(this).data('refid');
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

  $('#reflexes tfoot th').each(function() {
    var title = $(this).text();
    $(this).html('<input type="text" placeholder="Search ' + title + '" />');
  });

  $('#protoforms tfoot th').each(function() {
    var title = $(this).text();
    $(this).html('<input type="text" placeholder="Search ' + title + '" />');
  });

  var supporting = $('#supporting').DataTable({
    select: true,
    serverSide: true,
    ajax: {
      url: "/supporting",
      type: "GET",
      data: function(d) {
        d.prefid = window.prefid;
      }
    }
  });

  var protoforms = $('#protoforms').DataTable({
    dom: 'Blrtp',
    select: {
      style: 'single'
    },
    serverSide: true,
    ajax: {
      url: "/protoforms",
      type: "GET"
    },
    buttons: [
      {
        text: 'Edit',
        action: editProtoform
      }
    ]
  });

  var reflexes = $('#reflexes').DataTable({
    dom: 'Blrtp',
    select: true,
    serverSide: true,
    ajax: {
      url: "/reflexes",
      type: "GET"
    },
    columns: [{
        orderable: false,
        searchable: false
      },
      null,
      null,
      null
    ],
    buttons: [{
        text: 'Add',
        action: addReflexesToSupportingForms
      },
      {
        text: 'Edit',
        action: editReflexes
      }
    ]
  });

  // Apply the search
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
    window.prefid = protoforms.rows(indexes).data().toArray()[0][0];
    console.log(window.prefid);
    supporting.draw();
  });
});
