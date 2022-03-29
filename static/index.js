$(document).ready(function() {
    //Hide loading_sing until submit is clicked
    $('#loading_sign').hide();
    $('#load_span').hide();
    //Hide the events container unless user chooses to use calendar events
    $('#events_container_label').hide();
    $('#events_container').hide();
    //Hides the song inputs for events unless user chooses to use use the event
    $('input[type="checkbox"]').not("#use_calendar_state_checkbox").each(function() {
        var inputValue = $(this).attr("value");
        $("." + inputValue).hide();
    });
    
    //When the user toggles between using calendar events and not, the appropriate inputs are shown/hidden
    $('#use_calendar_state_checkbox').change(function() {            
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
            $('#first_song_label').hide();
            $('#first_song').hide();
            $('#steps_label').hide();
            $('#steps_input').hide();
            $('#events_container_label').show();
            $('#events_container').show();
            $(".non-events").each(function() {
                $(this).prop('required', false);
                console.log("removed required" + $(this).attr("id"));
            });
        } else {
            $('#first_song_label').show();
            $('#first_song').show();
            $('#steps_label').show();
            $('#steps_input').show();
            $('#events_container_label').hide();
            $('#events_container').hide();
            $(".non-events").each(function() {
                $(this).prop('required', true);
                console.log("added required" + $(this).attr("id"));
            });
        }
    });
    //When the user toggles between using an event and not, the song input for that event is shown/hidden
    $('input[type="checkbox"]').not("#use_calendar_state_checkbox").click(function() {
        var inputValue = $(this).attr("value");
        if ($(this).is(":checked")) {
            $("." + inputValue).prop('required', true);
            $("." + inputValue).show();
        } else {
            $("." + inputValue).prop('required', false);
            $("." + inputValue).hide();
        }
    });
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
        }
    });

});