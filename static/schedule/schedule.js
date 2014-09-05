$(document).ready(function() {
  
  $(".appointment-start-datetime").datetimepicker({
      minDate: moment(),
      pick12HourFormat: false
  });

  $(".appointment-end-datetime").datetimepicker({
      minDate: moment(),
      pick12HourFormat: false
  });

  $(".appointment-datetime-input").click(function() {
      var $parent = $(this.parentNode);
      var $button = $parent.find(".appointment-datetime-button");
      $button.parent().data("DateTimePicker").show();
  });

  $("#appointmentForm").ready(function() {
      var tz = $(this).find('input[name="timezone"]');
      tz.val( moment().zone() );
  });

  // some global variables, that are used in every event* . 

  dialogContent = $("#event_edit_container");
  titleField = dialogContent.find("input[name='title']");
  bodyField = dialogContent.find("textarea[name='body']");
  startField = dialogContent.find("select[name='start']");
  endField = dialogContent.find("select[name='end']");
      
    
  //the following fields appear only to the professor
  courseField = dialogContent.find("select[name='course_id']");
  typeField = dialogContent.find("select[name='type']");
  addToOtherWeeks = dialogContent.find("input[name='copy']");
      
  courseLabel = dialogContent.find("#courseLabel");
  copyLabel = dialogContent.find("#copyLabel");
  form = dialogContent.find("form[id='appointmentForm']");
      
      

  var $calendar = $('#calendar');
  $('#calendar').weekCalendar({
    data: eventData,

    timeslotsPerHour: 4,
    allowCalEventOverlap: true,
    overlapEventsSeparate: true,
    totalEventsWidthPercentInOneColumn : 100,
    
    
    height: function($calendar) {
      return $(window).height() - $('h1').outerHeight(true);
    },

    eventRender: function(calEvent, $event) {
      if (calEvent.end.getTime() < new Date().getTime() || (!calEvent.modifiable)) {
        $event.css('backgroundColor', '#aaa');
        $event.find('.time').css({
          backgroundColor: '#999',
          border:'1px solid #888'
        });
      }
    },
    
    eventNew: function(calEvent, $event) {
      prepareFields(dialogContent,calEvent);
      
      courseLabel.hide();
      //defaults to Personal.
      typeField.val('0');

      typeField.change(function(){
          if (typeField.val() === '0'){ // personal appointment
            courseLabel.hide(400);
          }else{ // course appointment
            courseLabel.show(400);
          }
          
      });

      dialogContent.dialog({
          modal: true,
          title: "New Appointment",
          
          close: function() {
             dialogContent.dialog("destroy");
             dialogContent.hide();
             $('#calendar').weekCalendar("removeUnsavedEvents");
          },
          
          buttons: {
             save : function() {
                
                var startField = dialogContent.find("#start");
                var endField = dialogContent.find("#end");

                $calendar.weekCalendar("removeUnsavedEvents");
                dialogContent.dialog("close");
                // if the user is not a professor, or if the user is a professor and he/she wants to add a personal appointment
                if( courseField.val() === undefined || typeField.val() === undefined || typeField.val() === "0"){
                  $.ajax({
                    type:form.attr("method"),
                    url:"add_personal_appointment",
                    data: form.serialize(),
                    
                    success: function(data){                    
                      
                      data = $.parseJSON(data);
                      if(data.status === 'OK'){

                        for(var i=0;i<data.appointments.length;i++){
                          appointment = data.appointments[i];
                          alert(appointment);
                          eventData.events.push(appointment);
                        }
                        
                        data: eventData;
                      
                      }
                    }

                  });
                }
                else{ // the user is a professor
                  $.ajax({
                    type:form.attr("method"),
                    url:"add_course_appointment",
                    data: form.serialize(),
                    success: function(data){
                      if(data.status === 'OK'){
                        eventData.events.push({
                          'id' : data.eventId,
                          'title': titleField.val(),
                          'body': bodyField.val(), 
                          'start': new Date(startField.val()), 
                          'end': new Date(endField.val()),
                          'courseName': courseField.val(),
                          'type':'Course', 
                          'modifiable': true,
                        });

                        data: eventData;



                      }
                    }

                  });
                }
              },
                
              cancel : function() {
                $calendar.weekCalendar("removeUnsavedEvents");
                dialogContent.dialog("destroy");
             }
          }
      }).show();
      
      var startField = dialogContent.find("select[name='start']").val(calEvent.start);
      var endField = dialogContent.find("select[name='end']").val(calEvent.end);
      dialogContent.find(".date_holder").text($calendar.weekCalendar("formatDate", calEvent.start));
      setupStartAndEndTimeFields(startField, endField, calEvent, $calendar.weekCalendar("getTimeslotTimes", calEvent.start));
      //setupCourseFields(courses,calEvent,courseField);
      dialogContent.find("select[name='type']").attr('disabled', false);
      dialogContent.find("select[name='course_id']").attr('disabled', false);
    },

    eventDrop: function(calEvent, $event) {
      if (calEvent.readOnly || !calEvent.modifiable) {
          return;
      }

       prepareFields(dialogContent,calEvent);
       
       if(calEvent.type === 'Personal'){
        typeField.val("0");
       }
       if(calEvent.type === 'Course'){
        typeField.val("1");
       }

       copyLabel.hide();
       
       dialogContent.find("input[name='eventId']").val(calEvent.id);
       
       setupCourseFields(calEvent);

      if(calEvent.type === 'Course'){
          $.ajax({
            headers: { "X-CSRFToken": getCookie("csrftoken") },
            type:form.attr("method"),
            url:"resize_appointment",
            data:form.serialize(),
            success: function(data){
              for(var i = 0 ; i < eventData.events.length; i++){
                var e = eventData.events[i];
                if(e.id === calEvent.id){
                  eventData.events.splice(i,1);
                }
              }
                eventData.events.push({
                        'id' : calEvent.id,
                        'title': calEvent.title,
                        'body': calEvent.body, 
                        'start': calEvent.start, 
                        'end': calEvent.end,
                        'type':'Course',
                        'courseName':calEvent.courseName,
                        'modifiable' :true,
                });
            }
          });
       }else if(calEvent.type === 'Personal'){
          $.ajax({
            headers: { "X-CSRFToken": getCookie("csrftoken") },
            type:form.attr("method"),
            url:"resize_appointment",
            data:form.serialize(),
            success: function(){
              for(var i = 0 ; i < eventData.events.length; i++){
                var e = eventData.events[i];
                if(e.id === calEvent.id){
                  eventData.events.splice(i,1);
                }
              }
                eventData.events.push({
                        'id' : calEvent.id,
                        'title': calEvent.title,
                        'body': calEvent.body, 
                        'start': calEvent.start, 
                        'end': calEvent.end,
                        'type':'Personal',
                        'modifiable' :true,
                });
              }
          });
        }
    },

    eventResize: function(calEvent, $event) {
      if (calEvent.readOnly || !calEvent.modifiable) {
          return;
      }

       prepareFields(dialogContent,calEvent);
      
       if(calEvent.type === 'Personal'){
        typeField.val("0");
       }
       if(calEvent.type === 'Course'){
        typeField.val("1");
       }

      copyLabel.hide();
       
      dialogContent.find("input[name='eventId']").val(calEvent.id);
      
      setupCourseFields(calEvent);

      if(calEvent.type === 'Course'){
          $.ajax({
            headers: { "X-CSRFToken": getCookie("csrftoken") },
            type:form.attr("method"),
            url:"resize_appointment",
            data:form.serialize(),
            success: function(data){
              for(var i = 0 ; i < eventData.events.length; i++){
                var e = eventData.events[i];
                if(e.id === calEvent.id){
                  eventData.events.splice(i,1);
                }
              }
                eventData.events.push({
                        'id' : calEvent.id,
                        'title': calEvent.title,
                        'body': calEvent.body, 
                        'start': calEvent.start, 
                        'end': calEvent.end,
                        'type':'Course',
                        'courseName':calEvent.courseName,
                        'modifiable' :true,
                });
            }
          });
       }else if(calEvent.type === 'Personal'){
          $.ajax({
            headers: { "X-CSRFToken": getCookie("csrftoken") },
            type:form.attr("method"),
            url:"resize_appointment",
            data:form.serialize(),
            success: function(){
              for(var i = 0 ; i < eventData.events.length; i++){
                var e = eventData.events[i];
                if(e.id === calEvent.id){
                  eventData.events.splice(i,1);
                }
              }
                eventData.events.push({
                        'id' : calEvent.id,
                        'title': calEvent.title,
                        'body': calEvent.body, 
                        'start': calEvent.start, 
                        'end': calEvent.end,
                        'type':'Personal',
                        'modifiable' :true,
                });
              }
          });
        }
    },

    // to modify existing calEvents (or remove them)
    eventClick: function(calEvent, $event) {
      
      if (calEvent.readOnly || !calEvent.modifiable) {
          return;
       }
    
       prepareFields(dialogContent,calEvent);
       titleField.val(calEvent.title);
       bodyField.val(calEvent.body);
       
       
       if(calEvent.type === 'Personal'){
        typeField.val("0");
       }
       if(calEvent.type === 'Course'){
        typeField.val("1");
       }

       
       dialogContent.find("input[name='eventId']").val(calEvent.id);
       
       setupCourseFields(calEvent);
      
       if(calEvent.type === 'Personal'){
        courseLabel.hide();
       }
        
       dialogContent.dialog({
          modal: true,
          title: "Edit",
          close: function() {
             dialogContent.dialog("destroy");
             dialogContent.hide();
             $('#calendar').weekCalendar("removeUnsavedEvents");
          },
          buttons: {
            save : function() {
                //reenable the 'select' to serialize the form, otherwise a KeyError is raised.
                //it is set to true again after the ajax request is sent
                dialogContent.find("select[name='course_id']").attr('disabled', false);

                if(calEvent.type === 'Course' && calEvent.modifiable){
                  $.ajax({
                    type:form.attr("method"),
                    url:"edit_course_appointment",
                    data: form.serialize(),
                    success: function(data){
                      //alert("Successfuly edited event");
                      $calendar.weekCalendar("updateEvent", calEvent);
                      $calendar.weekCalendar("refresh");
                      dialogContent.dialog("close");
                    }
                  });
                }else if(calEvent.type === 'Personal'){
                    $.ajax({
                      type:form.attr("method"),
                      url:"edit_personal_appointment",
                      data: form.serialize(),
                      success: function(data){
                        //alert("Successfuly edited event");
                        $calendar.weekCalendar("updateEvent", calEvent);
                        $calendar.weekCalendar("refresh");
                      }
                    });

                  $calendar.weekCalendar("updateEvent", calEvent);
                  $calendar.weekCalendar("refresh");
                  dialogContent.dialog("close");
                }  

                dialogContent.find("select[name='course_id']").attr('disabled', true);

             },

            "delete" : function() {
                
                $calendar.weekCalendar("removeEvent", calEvent.id);
                dialogContent.dialog("destroy");
                
                if(calEvent.type === 'Personal' && calEvent.modifiable){
                  $.ajax({
                    headers: { "X-CSRFToken": getCookie("csrftoken") },
                    type:"POST",
                    url:"remove_personal_appointment",
                    data: {
                      'id' : calEvent.id,
                    },
                    success: function(){
                      //alert("Successfuly removed event");
                      for(var i = 0 ; i < eventData.events.length; i++){
                        var e = eventData.events[i];
                        if(e.id === calEvent.id){
                          eventData.events.splice(i,1);
                        }
                      }

                      data:eventData;

                    }
                  });
                }else if(calEvent.type === 'Course' && calEvent.modifiable){
                  $.ajax({
                    headers: { "X-CSRFToken": getCookie("csrftoken") },
                    type:"POST",
                    url:"remove_course_appointment",
                    data: {
                      'id' : calEvent.id,
                      'courseName': calEvent.courseName,
                    },
                    success: function(){
                      //alert("Successfuly removed event");
                      for(var i = 0 ; i < eventData.events.length; i++){
                        var e = eventData.events[i];
                        if(e.id === calEvent.id){
                          eventData.events.splice(i,1);
                        }
                      }

                      data:eventData;

                    }
                  });
                }
             },
             
            cancel : function() {
                dialogContent.dialog("close");
             }
          }
       }).show();

       var startField = dialogContent.find("select[name='start']").val(calEvent.start);
       var endField = dialogContent.find("select[name='end']").val(calEvent.end);
       dialogContent.find(".date_holder").text($calendar.weekCalendar("formatDate", calEvent.start));
       setupStartAndEndTimeFields(startField, endField, calEvent, $calendar.weekCalendar("getTimeslotTimes", calEvent.start));
       setupCourseFields(calEvent);
       dialogContent.find("select[name='type']").attr('disabled', true);
       dialogContent.find("select[name='course_id']").attr('disabled', true)
    },

    eventMouseover: function(calEvent, $event) {
      displayMessage('<strong>Mouseover Event</strong><br/>Start: ' + calEvent.start + '<br/>End: ' + calEvent.end);
    },

    eventMouseout: function(calEvent, $event) {
      displayMessage('<strong>Mouseout Event</strong><br/>Start: ' + calEvent.start + '<br/>End: ' + calEvent.end);
    },

    noEvents: function() {
      displayMessage('There are no events for this week. YAY!');
    }

  });

function displayMessage(message) {
  $('#message').html(message).fadeIn();
}

function prepareFields(dialogContent,calEvent) {
  dialogContent.find(".to-reset").val("");

  $("#start_dp").data("DateTimePicker").setDate(moment(new Date(calEvent.start)));
  $("#end_dp").data("DateTimePicker").setDate(moment(new Date(calEvent.end)));

  dialogContent.find("select[name='course']").empty();
}

function getCookie(c_name){
    if (document.cookie.length > 0)
    {
        c_start = document.cookie.indexOf(c_name + "=");
        if (c_start != -1)
        {
            c_start = c_start + c_name.length + 1;
            c_end = document.cookie.indexOf(";", c_start);
            if (c_end == -1) c_end = document.cookie.length;
            return unescape(document.cookie.substring(c_start,c_end));
        }
    }
    return "";
 }


function setupStartAndEndTimeFields($startTimeField, $endTimeField, calEvent, timeslotTimes) {
  for (var i = 0; i < timeslotTimes.length; i++) {
    var startTime = timeslotTimes[i].start;
    var endTime = timeslotTimes[i].end;
    var startSelected = "";
    if (startTime.getTime() === calEvent.start.getTime()) {
      startSelected = "selected=\"selected\"";
    }
    var endSelected = "";
    if (endTime.getTime() === calEvent.end.getTime()) {
      endSelected = "selected=\"selected\"";
    }
    $startTimeField.append("<option value=\"" + startTime + "\" " + startSelected + ">" + timeslotTimes[i].startFormatted + "</option>");
    $endTimeField.append("<option value=\"" + endTime + "\" " + endSelected + ">" + timeslotTimes[i].endFormatted + "</option>");

  }
  
  $endTimeOptions = $endTimeField.find("option");
  $startTimeField.trigger("change");
}


function setupCourseFields(calEvent){
  $("select[name='course_id'] option").each(function(){
    if(calEvent.type === 'Personal')
      return;

    if(calEvent.courseName.trim() === $(this).text().trim()){
      $(this).attr('selected', true);  
    }
  });
  courseField.trigger("change");
}

var $endTimeField = $("select[name='end']");
var $endTimeOptions = $endTimeField.find("option");

//reduces the end time options to be only after the start time options.
$("select[name='start']").change(function() {
  var startTime = $(this).find(":selected").val();
  var currentEndTime = $endTimeField.find("option:selected").val();
  $endTimeField.html(
        $endTimeOptions.filter(function() {
           return startTime < $(this).val();
        })
        );

  var endTimeSelected = false;
  $endTimeField.find("option").each(function() {
     if ($(this).val() === currentEndTime) {
        $(this).attr("selected", "selected");
        endTimeSelected = true;
        return false;
     }
  });

  if (!endTimeSelected) {
     //automatically select an end date 2 slots away.
     $endTimeField.find("option:eq(1)").attr("selected", "selected");
  }

});



});