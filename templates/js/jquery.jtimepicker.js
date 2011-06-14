/*
 * jTimepicker plugin 1.4.1
 *
 * http://www.radoslavdimov.com/jquery-plugins/jquery-plugin-jtimepicker/
 *
 * Copyright (c) 2009 Radoslav Dimov
 *
 * Dual licensed under the MIT and GPL licenses:
 * http://www.opensource.org/licenses/mit-license.php
 * http://www.gnu.org/licenses/gpl.html
 *
 * Depends:
 *      ui.core.js
 *      ui.slider.js
 */

(function($) {
    $.fn.extend({
		
        jtimepicker: function(options) {
            
            var defaults = {
                clockIcon: 'images/icon_clock_2.gif',
                orientation: 'horizontal',
                // set hours
                hourCombo: 'hourcombo',
                hourMode: 24,
                hourInterval: 1,
                hourDefaultValue: 0,
                hourSlider: 'hourSlider',
                hourLabel: 'hour',
                // set minutes
                minCombo: 'mincombo',
                minLength: 60,
                minInterval: 5,
                minDefaultValue: 0,
                minSlider: 'minSlider',
                minLabel: 'min',
                // set seconds
                secView: true,
                secCombo: 'seccombo',
                secLength: 60,
                secInterval: 5,
                secDefaultValue: 0,
                secSlider: 'secSlider',
                secLabel: 'sec'
            };

            var options = $.extend(defaults, options);
            
            return this.each(function() {
                var o = options;
                var $this = $(this);
                var html = '';
                var orientation = (o.orientation == 'horizontal') ? 'auto' : 'vertical';
                var sliderData = [
                                    {'label':o.hourLabel, 'slider':o.hourSlider, 'combo':o.hourCombo},
                                    {'label':o.minLabel, 'slider':o.minSlider, 'combo':o.minCombo}
                                    ];

                
                
                html += $this.createCombo(o.hourCombo, o.hourMode, o.hourInterval, o.hourDefaultValue);
                html += $this.createCombo(o.minCombo, o.minLength, o.minInterval, o.minDefaultValue);
                if (o.secView) {
                    sliderData.push({'label':o.secLabel, 'slider':o.secSlider, 'combo':o.secCombo});
                    html += $this.createCombo(o.secCombo, o.secLength, o.secInterval, o.secDefaultValue);
                }
                html += '<img src="' + o.clockIcon + '" class="clock" />';
                html += $this.createSliderWrap(sliderData);
                $this.html(html);
                
                $('#sliderWrap').addClass(orientation);
                
                $this.createSlider(o.hourSlider, o.hourMode, o.hourCombo, o.hourInterval, o.hourDefaultValue, o.orientation);
                $this.createSlider(o.minSlider, o.minLength, o.minCombo, o.minInterval, o.minDefaultValue, o.orientation);
                if (o.secView) {
                    $this.createSlider(o.secSlider, o.secLength, o.secCombo, o.secInterval, o.secDefaultValue, o.orientation);
                }

                $.each(sliderData, function(i, item) {
                    $('.' + item.combo).change(function() {
                        var val = $(this).val();
                        $('.' + item.slider).slider('option', 'value', val);
                    });
                });                

                $this.find('.clock').click(function() {
                    $this.find('#sliderWrap').toggle(function() {
                        $(document).click(function(event) {
                            if (!($(event.target).is('#sliderWrap') || $(event.target).parents('#sliderWrap').length || $(event.target).is('.clock'))) {
                                $this.find('#sliderWrap').hide(500);
                            }
                        });
                    });  
                });              
            }); 
        }     
    });

    $.fn.createCombo = function(id, length, interval, defValue) {
        var html = '<select class="' + id + ' combo" name="' + id + '">';
        for(i = 0; i < length; i += interval) {
            var selected = i == defValue ? ' selected="selected"' : '';
            var txt = i < 10 ? '0' + i : i;
            html += '<option value="' + i + '"' + selected + '>' + txt + '</option>';
        }
        html += "</select>";

        return html;
    }

    $.fn.createSliderWrap = function(data) {
        var html = '<div id="sliderWrap">';
        $.each(data, function(i, item) {
            html += '   <div><label>' + item.label + ':</label> <p class="' + item.slider + '"></p></div>';
        });
            html += '</div>';

        return html;
    }

    $.fn.createSlider = function(id, maxValue, combo, stepValue, defValue, orientation) {
        var $this = $(this);
        $this.find('.' + id).slider({
            orientation: orientation,
            range: "min",
            min: 0,
            max: maxValue - stepValue,
            value: defValue,
            step: stepValue,
            animate: true ,
            slide: function(event, ui) {
                $this.find('.' + combo).val(ui.value);
            }            
        });
    }


})(jQuery);
