$(document).ready(function() {
    //Hide loading_sing until submit is clicked
    $('#loading_sign').hide();
    $('#load_span').hide();
    //Hide the events container unless user chooses to use calendar events
    $('#events_container_label').hide();
    $('#events_container').hide();
    $('#event_date_select').hide();
    //Hides the song inputs for events unless user chooses to use use the event
    $('input[type="checkbox"]').not("#use_calendar_state_checkbox").each(function() {
        var inputValue = $(this).attr("value");
        $("." + inputValue).hide();
    });
    //to prevent loading circle from being misaligned
    $(".card_body").css("position", "unset"); 

    //Set placeholder date to today's date
    today = new Date()
    $('#event_date_select').val(today.toISOString().substring(0, 10));
    $('#event_date_select').attr("min", today.toISOString().substring(0, 10));
    today.setMonth(today.getMonth() + 3);
    $('#event_date_select').attr("max", today.toISOString().substring(0, 10));
    today.setMonth(today.getMonth() - 3);
    //Loads the events for today by default
    events = $("#events").val()
    events = events.replace(/'/g, '"')
    events = JSON.parse(events);
    today = today.toISOString().substring(0,10)
    if (events[today] != undefined) {
        console.log("Today's events:", events[today])
        let i = 1;
        events[today].forEach(function(event, i) {
            console.log(Object.keys(event));
            $('#events_container').append(
                '<input name="event_'+i+'_checkbox" type="checkbox" id="event_'+i+'_checkbox" value="'+event.summary+'">'+
                '<label class="event_checkbox_labels" for="event_'+i+'_checkbox">'+event.summary+' at '+event.start.dateTime.substring(11,16)+'</label>'+
                '<input name="event_'+i+'_'+event.summary+'_song" type="text" class="'+event.summary+' selectt" id="event_'+i+'_song_input" placeholder="Enter First Song"><br>'
            )
            $('#event_'+i+'_song_input').hide();
            bind_checkbox_to_song_input(i);
        })
    }


    //When the user toggles between using calendar events and not, the appropriate inputs are shown/hidden
    $('#use_calendar_state_checkbox').change(function() { 
        console.log("use_calendar_state_checkbox changed");           
        //Uncheck checkboxes when the user clicks the state checkbox
        $('input[type="checkbox"]').not("#use_calendar_state_checkbox").each(function() {
            $(this).prop('checked', false);
        });
        //Clear the song inputs when the user clicks the state checkbox
        $('input[type="text"]').each(function() {
            $(this).val("");
            if($(this).hasClass("selectt")) {
                $(this).hide();
            }
        });
        if ($(this).is(":checked")) {
            console.log("showing stuff")
            $('#first_song_label').hide();
            $('#first_song').hide();
            $('#steps_label').hide();
            $('#steps_input').hide();
            $('#events_container_label').show();
            $('#events_container').show();
            $('#event_date_select').show();
            $(".non-events").each(function() {
                $(this).prop('required', false);
                console.log("removed required" + $(this).attr("id"));
            });
        } else {
            console.log("showing other stuff")
            $('#first_song_label').show();
            $('#first_song').show();
            $('#steps_label').show();
            $('#steps_input').show();
            $('#events_container_label').hide();
            $('#events_container').hide();
            $('#event_date_select').hide();
            $(".non-events").each(function() {
                $(this).prop('required', true);
                console.log("added required" + $(this).attr("id"));
            });
        }
    });
    function bind_checkbox_to_song_input(i) {
        $('#event_'+i+'_checkbox').click(function() {
            current_song_input=$('#event_'+i+'_song_input')
            console.log("displaying song input for event")
            var inputValue = $(this).attr("value");
            if ($(this).prop("checked")) {
                current_song_input.prop('required', true);
                current_song_input.show();
            } else {
                current_song_input.prop('required', false);
                current_song_input.hide();
            }
        });
    }
    //When the user selects a different date, display the events for that date
    $('#event_date_select').change(function() {
        //Clear currently displayed events
        $('#events_container').empty();
        //Loads the events for specified date
        events = $("#events").val()
        events = events.replace(/'/g, '"')
        events = JSON.parse(events);
        selected_date = $('#event_date_select').val()
        if (events[selected_date] != undefined) {
            console.log("Today's events:", events[selected_date])
            events[selected_date].forEach(function(event, i) {
                $('#events_container').append(
                    '<input name="event_'+i+'_checkbox" type="checkbox" id="event_'+i+'_checkbox" value="'+event.summary+'">'+
                    '<label class="event_checkbox_labels" for="event_'+i+'_checkbox">'+event.summary+' at '+event.start.dateTime.substring(11,16)+'</label>'+
                    '<input name="event_'+i+'_'+event.summary+'_song" type="text" class="'+event.summary+' selectt" id="event_'+i+'_song_input" placeholder="Enter First Song"><br>'
                )
                $('#event_'+i+'_song_input').hide();
                bind_checkbox_to_song_input(i);
            })
        }
    })
    //When the user toggles between using an event and not, the song input for that event is shown/hidden
    // function bindCheckboxToggle() {
    //     $('input[type="checkbox"]').not("#use_calendar_state_checkbox").click(function() {
    //         console.log("displaying song input for event")
    //         var inputValue = $(this).attr("value");
    //         if ($(this).is(":checked")) {
    //             $("." + inputValue).prop('required', true);
    //             $("." + inputValue).show();
    //         } else {
    //             $("." + inputValue).prop('required', false);
    //             $("." + inputValue).hide();
    //         }
    //     });
    // }
    
    //At least one checkbox in the events container must be checked if the user chooses to use calendar events
    $("#submit_button").click(function(event) {
        let checked = false;
        let events_have_songs = true;
        let submitted = true;
        //Check that each checked event has a corresponding songs - loading bar doesn't appear otherwise
        $('input[type="checkbox"]').not("#use_calendar_state_checkbox").each(function() {
            console.log("value of input: ", $(this).attr("id"))
            if ($(this).is(":checked")) {
                checked = true;
                //Get corresponding input song and check if it's empty
                input_id = "#event_" + $(this).attr("id").replace("event_", "").replace("_checkbox", "") + "_song_input"
                if($(input_id).val().length === 0) {
                    events_have_songs = false
                }
            }
        });
        if (!checked && $('#use_calendar_state_checkbox').is(":checked")) {
            alert("At least one event must be selected");
            submitted = false;
            event.preventDefault();
        }

        //Check valid steps(integer) input on submit button click (only if not using events)
        if(!$('#use_calendar_state_checkbox').is(":checked") && !Number.isInteger(parseInt($("#steps_input").val()))) {
            console.log(parseInt($("#steps_input").val()));
            submitted = false;
            alert("Steps input must be an integer!");
            event.preventDefault();
        } else if(!$('#use_calendar_state_checkbox').is(":checked")){
            $("#steps_input").val(parseInt($("#steps_input").val())) // prevent error in case input is non-integer
        }
        if(submitted && events_have_songs) {                
            //Submit is successful - show the loading animation
            $("#loading_sign").show();
            $('#load_span').show();
            //Set value of last checked event
            i=0;
            $('input[type="checkbox"]').not("#use_calendar_state_checkbox").each(function() {
                if ($(this).is(":checked")) {
                    $("#last_selected_event").val(i);
                }
                i++;
            });
            //specific data events
            event_date_select = $('#event_date_select').val()
            raw_events = $('#events').val()
            raw_events = raw_events.replace(/'/g, '"')
            date_selected_events = JSON.parse(raw_events)
            date_selected_events=JSON.stringify(date_selected_events[event_date_select])
            $('#events').val(date_selected_events)
        }
    });

});