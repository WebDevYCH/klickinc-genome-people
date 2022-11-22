import ready, {HTML} from './utils';
import initCustomSelect from './components/initCustomSelect';
import {initdatepicker, currentDate} from './components/initDatepicker';
import initTabs from './components/initTabs';
import initOpenClose from './components/initOpenClose';
import initHasDropDown from './components/initHasDropDown';
import initExpandAll from './components/expandAll';
import initFiltering from './components/filtering';
import initSearch from './components/search';
import initTooltip from './components/initTooltip';

ready(() => {
	HTML.classList.add('is-loaded');
	initCustomSelect();
	currentDate();
	initdatepicker();
	initTabs();
	initHasDropDown();
	initOpenClose();
	initExpandAll();
	initFiltering();
	initSearch();
	initTooltip();
});