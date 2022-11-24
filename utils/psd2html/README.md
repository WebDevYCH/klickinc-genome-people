# Webpack build for optimized load speed

#### Requirements

* [Node JS](https://nodejs.org/) - install the latest recommended version(**minimal version is 10**)

If you have Node JS already installed, please check version and make sure it is 10+:
* `node -v` - **If your version is earlier than 10 - upgrade your Node JS**

## How to use

1. Install project dependencies: (**_if you already have modules installed, please skip this step_**)
```
#Using npm
npm i

#Using yarn
yarn
```
Make sure your location is root of `markup` folder

2.  To run development mode, run:
```
#Using npm
npm run dev

#Using yarn
yarn dev
```

3.  To compile all assests into production mode, run:
```
#Using npm
npm run build

#Using yarn
yarn build
```
Build assets intro `dist` folder

**Additional utility scripts:**

1. Run local webserver
```
#Using npm
npm run preview

#Using yarn
yarn preview
```
To preview builded assets, for example. Used module `serve` under the hood.

2. Prettify HTML after compilation
```
#Using npm
npm run prettify:html

#Using yarn
yarn prettify:html
```
Uses Prettier to prettify HTML files from `dist` folder. Can be used only after compilation process.

**_Don't use `npm` and `yarn` in the same project - this can lead to unexpected results_**
