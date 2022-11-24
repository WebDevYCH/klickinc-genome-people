/* eslint-disable */

/*
 * jQuery Open/Close plugin
 */
(function($) {
  function OpenClose(options) {
    this.options = $.extend(
      {
        addClassBeforeAnimation: true,
        hideOnClickOutside: false,
        activeClass: 'active',
        opener: '.opener',
        slider: '.slide',
        animSpeed: 400,
        effect: 'fade',
        event: 'click',
      },
      options
    );
    this.init();
  }
  OpenClose.prototype = {
    init() {
      if (this.options.holder) {
        this.findElements();
        this.attachEvents();
        this.makeCallback('onInit', this);
      }
    },
    findElements() {
      this.holder = $(this.options.holder);
      this.opener = this.holder.find(this.options.opener);
      this.slider = this.holder.find(this.options.slider);
    },
    attachEvents() {
      // add handler
      const self = this;
      this.eventHandler = function(e) {
        e.preventDefault();
        if (self.slider.hasClass(slideHiddenClass)) {
          self.showSlide();
        } else {
          self.hideSlide();
        }
      };
      self.opener.on(self.options.event, this.eventHandler);

      // hover mode handler
      if (self.options.event === 'hover') {
        self.opener.on('mouseenter', function() {
          if (!self.holder.hasClass(self.options.activeClass)) {
            self.showSlide();
          }
        });
        self.holder.on('mouseleave', function() {
          self.hideSlide();
        });
      }

      // outside click handler
      self.outsideClickHandler = function(e) {
        if (self.options.hideOnClickOutside) {
          const target = $(e.target);
          if (!target.is(self.holder) && !target.closest(self.holder).length) {
            self.hideSlide();
          }
        }
      };

      // set initial styles
      if (this.holder.hasClass(this.options.activeClass)) {
        $(document).on('click touchstart', self.outsideClickHandler);
      } else {
        this.slider.addClass(slideHiddenClass);
      }
    },
    showSlide() {
      const self = this;
      if (self.options.addClassBeforeAnimation) {
        self.holder.addClass(self.options.activeClass);
      }
      self.slider.removeClass(slideHiddenClass);
      $(document).on('click touchstart', self.outsideClickHandler);

      self.makeCallback('animStart', true);
      toggleEffects[self.options.effect].show({
        box: self.slider,
        speed: self.options.animSpeed,
        complete() {
          if (!self.options.addClassBeforeAnimation) {
            self.holder.addClass(self.options.activeClass);
          }
          self.makeCallback('animEnd', true);
        },
      });
    },
    hideSlide() {
      const self = this;
      if (self.options.addClassBeforeAnimation) {
        self.holder.removeClass(self.options.activeClass);
      }
      $(document).off('click touchstart', self.outsideClickHandler);

      self.makeCallback('animStart', false);
      toggleEffects[self.options.effect].hide({
        box: self.slider,
        speed: self.options.animSpeed,
        complete() {
          if (!self.options.addClassBeforeAnimation) {
            self.holder.removeClass(self.options.activeClass);
          }
          self.slider.addClass(slideHiddenClass);
          self.makeCallback('animEnd', false);
        },
      });
    },
    destroy() {
      this.slider.removeClass(slideHiddenClass).css({
        display: '',
      });
      this.opener.off(this.options.event, this.eventHandler);
      this.holder.removeClass(this.options.activeClass).removeData('OpenClose');
      $(document).off('click touchstart', this.outsideClickHandler);
    },
    makeCallback(name) {
      if (typeof this.options[name] === 'function') {
        const args = Array.prototype.slice.call(arguments);
        args.shift();
        this.options[name].apply(this, args);
      }
    },
  };

  // add stylesheet for slide on DOMReady
  var slideHiddenClass = 'js-slide-hidden';
  (function() {
    const tabStyleSheet = $('<style type="text/css">')[0];
    let tabStyleRule = `.${slideHiddenClass}`;
    tabStyleRule += '{position:absolute !important;left:-9999px !important;top:-9999px !important;display:block !important}';
    if (tabStyleSheet.styleSheet) {
      tabStyleSheet.styleSheet.cssText = tabStyleRule;
    } else {
      tabStyleSheet.appendChild(document.createTextNode(tabStyleRule));
    }
    $('head').append(tabStyleSheet);
  })();

  // animation effects
  var toggleEffects = {
    slide: {
      show(o) {
        o.box
          .stop(true)
          .hide()
          .slideDown(o.speed, o.complete);
      },
      hide(o) {
        o.box.stop(true).slideUp(o.speed, o.complete);
      },
    },
    fade: {
      show(o) {
        o.box
          .stop(true)
          .hide()
          .fadeIn(o.speed, o.complete);
      },
      hide(o) {
        o.box.stop(true).fadeOut(o.speed, o.complete);
      },
    },
    none: {
      show(o) {
        o.box.hide().show(0, o.complete);
      },
      hide(o) {
        o.box.hide(0, o.complete);
      },
    },
  };

  // jQuery plugin interface
  $.fn.openClose = function(opt) {
    const args = Array.prototype.slice.call(arguments);
    const method = args[0];

    return this.each(function() {
      const $holder = jQuery(this);
      const instance = $holder.data('OpenClose');

      if (typeof opt === 'object' || typeof opt === 'undefined') {
        $holder.data(
          'OpenClose',
          new OpenClose(
            $.extend(
              {
                holder: this,
              },
              opt
            )
          )
        );
      } else if (typeof method === 'string' && instance) {
        if (typeof instance[method] === 'function') {
          args.shift();
          instance[method].apply(instance, args);
        }
      }
    });
  };
})(jQuery);
