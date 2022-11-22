import './resizeHandler';
// import './vh'; - use it in case crosss browser vh value is needed

export const HTML = document.documentElement;
export const BODY = document.body;

/*
  "jQuery like" ready function:
  Usage:

  import ready from 'Utils/global';
  ready(() => init());
*/

export default Document.prototype.ready = (fn) => {
  if (fn && typeof fn === 'function') {
    document.addEventListener('DOMContentLoaded', () => {
      if (document.readyState === 'interactive' || document.readyState === 'complete') {
        return fn();
      }
    });
  }
};

/*
  Publish custom event
  Params:

  {eventName}: String - the name of custom event. Better to use as a variable or constant not to mess names
  {data}: Object - custom event information, e.g. node element, whatever. Accessible via event
  {once}: Bool - trigger only once or every time when called
  Exmaple:

  import {ev} from 'Utils/global';

  const eventName = 'PopupToggle';

  popup.on('click', () => {
    ev(eventName, {
      popup: this,
    })
  })

  document.addEventListener(eventName, event => {
    // this is data that we pass into custom event
    const eventData = event.detail;
    const popupInstance = eventData.popup;
  })
*/

export const ev = (eventName, data, target = document) => {
  const e = new CustomEvent(eventName, { detail: data });
  target.dispatchEvent(e);
};
