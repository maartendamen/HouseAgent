$(document).ready(function() {
	$('#add_device_button').click(function() {
		device_name 		= $("input#name").val();
		device_address		= $("input#address").val();
		device_interface 	= $("select#interface").val();
		device_class 		= $("select#class").val();
		device_type 		= $("select#type").val();
		
		var dataString = 'name=' + device_name + '&address=' + device_address + '&interface='
						+ device_interface + '&class=' + device_class + '&type=' + device_type;
		
		$.ajax({
			type: "POST",
			url: "/core/device_do_add/", 
			data: dataString,
			success: function() {
						alert("done!");
					 }
		});
	});

	$('#add_latitude_button').click(function() {
	alert("hoi");
		name 		= $("input#name").val();
		username	= $("input#username").val();
		password 	= $("input#password").val();
		
		var dataString = 'name=' + name + '&username=' + username + '&password='
						+ password;
		
		$.ajax({
			type: "POST",
			url: "/core/latitude_add_account_do/", 
			data: dataString,
			success: function() {
						alert("Account added!");
					 }
		});
	});


	$('#latitude_location_button').click(function() {
		location = $("input#name").val();
		var dataString = 'location=' + location;
		
		$.ajax({
			type: "POST",
			url: "/core/latitude_locations_add/", 
			data: dataString,
			success: function() {
						alert("Known location added!");
					 }
		});
	});

	$('#latitude_settings_button').click(function() {
		setting_location_detection = $("input#setting_location_detection").val();
				
		var dataString = 'setting_location_detection=' + setting_location_detection;
		
		$.ajax({
			type: "POST",
			url: "/core/latitude_settings_save/", 
			data: dataString,
			success: function() {
						alert("Settings saved!");
					 }
		});
	});

	$( "#slider" ).slider({
		value:100,
		min: 0,
		max: 500,
		step: 50,
		slide: function( event, ui ) {
			$( "#amount" ).val( "$" + ui.value );
		}
	});

	$('#MenuHeader ul li.dropdown > a').click(function(e)
	{
		var elem = this;
		console.log(elem);
	    $(".submenu").toggle();	
		return false;
	});
	
	$('#on_button').button();
	$('#off_button').button();
});