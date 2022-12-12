// Scan Result Chart Setup

var scan_chart_spectra;
var scan_chart_fest;
var scan_chart_obj;

function setup_fft_plot(){
	scan_chart_spectra = {
	    xs: {
	        'Spectra': 'x_spectra'
	    },
	    columns: [
	        ['x_spectra',0,0],
	        ['Spectra',0,0]
	    ],
	    type:'line'
	};

	scan_chart_peaks = {
	    xs: {
	        'Tone Estimates': 'x_fest'
	    },
	    columns: [
	        ['x_fest',0],
	        ['Tone Estimates',0]
	    ],
	    type:'scatter'
	};

	scan_chart_obj = c3.generate({
	    bindto: '#fft_plot',
	    data: scan_chart_spectra,
        tooltip: {
            format: {
                title: function (d) { return (d / 1000000).toFixed(3) + " MHz"; },
                value: function (value) { return value + " dB"; }
            }
        },
	    axis:{
	        x:{
	            tick:{
                    culling: {
                        max: window.innerWidth > 1100 ? 10 : 4
                    },
	                format: function (x) { return (x/1000000).toFixed(3); }
	            },
	            label:"Frequency (MHz)"
	        },
	        y:{
	            label:"Power (dB - Uncalibrated)"
	        }
	    },
	    point:{r:10}
	});


    $('.c3-axis-y').css('fill', 'white')
    $('.c3-axis-x').css('fill', 'white')
    $('.c3-legend-item text').css('fill', 'white')
}