/*
  This is utility script for __routes page.
  This script takes data passed from webpack (pages list etc)
  Then parse this data into HTML to show list of pages.
  Only used in __routes page, never appear in production.
*/

if (process.env && process.env.NODE_ENV === 'development') {
  const data = process.env;
  const list = document.getElementById('pages-list');

  data.ROUTES.forEach((route) => {
    const pageName = route.split('.')[0];
    const pageLink = `/${pageName}.html`;
    const li = document.createElement('li');
    const link = document.createElement('a');

    if (pageName === data.ROUTES_PAGE) return;

    link.setAttribute('href', pageLink);
    link.innerText = pageName;
    list.appendChild(li);
    li.appendChild(link);
  });
}
