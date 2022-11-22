const { existsSync } = require('fs');
const { address } = require('ip');
const { resolve, join, posix, dirname, basename, parse } = require('path');
const readdir = require('@jsdevtools/readdir-enhanced');
const webpack = require('webpack');
const chokidar = require('chokidar');
const WebpackNotifierPlugin = require('webpack-notifier');
const ErrorsPlugin = require('@soda/friendly-errors-webpack-plugin');
const HTMLWebpackPlugin = require('html-webpack-plugin');
const StyleLintPlugin = require('stylelint-webpack-plugin');
const ScriptExtHtmlWebpackPlugin = require('script-ext-html-webpack-plugin');
const MiniCssExtractPlugin = require('mini-css-extract-plugin');
const CopyWebpackPlugin = require('copy-webpack-plugin');
const TerserPlugin = require('terser-webpack-plugin');
const ImageminPlugin = require('imagemin-webpack-plugin').default;
const ImageminWebpWebpackPlugin = require('imagemin-webp-webpack-plugin');
const imageminMozjpeg = require('imagemin-mozjpeg');
const SVGSpritemapPlugin = require('svg-spritemap-webpack-plugin');
const BundleAnalyzerPlugin = require('webpack-bundle-analyzer').BundleAnalyzerPlugin;
const FixStyleOnlyEntriesPlugin = require('webpack-fix-style-only-entries');
const ESLintPlugin = require('eslint-webpack-plugin');
const config = require('./config.json');

const SRC = config.src;
const DEST = config.dest;
const PROD = 'production';
const ENV = process.env.NODE_ENV;
const HOST = config.server.host || 'localhost';
const isProduction = ENV === PROD;
const routesPage = config.templates.routes || '__routes';
const sitePages = config.templates.pages ? config.templates.pages : config.templates.src;
const PUBLIC_PATH = '';

const getAssetPath = (type, assetPath) => {
  if (type === SRC) {
    return posix.join(__dirname, config.src, assetPath);
  }
  return posix.join(__dirname, config.dest, assetPath);
};

const getAssetName = (dest, name, ext) => {
  return posix.join(dest, `${name}.${ext}`);
};

const getAllPagesExceptRoutes = () => {
  const templateFiles = readdir.sync(getAssetPath(SRC, sitePages), {
    deep: !config.templates.extension === 'html',
    filter: function (stats) {
      const filteredFiles = stats.isFile() && !stats.path.includes(routesPage) && stats.path !== '.DS_Store' && stats.path.includes(config.templates.extension);
      return stats.isFile() && filteredFiles;
    },
  });

  return templateFiles;
};

const postServerMessage = (port, host = HOST) => {
  const URL = `http://${host}:${port}`;
  const IP = `http://${address()}:${port}`;
  const routesPageURL = `${URL}/${routesPage}.html`;
  const RED = '\033[0;31m';
  const GREEN = '\033[0;32m';

  return console.log(`
    ${RED}---------------------------------------
    🎉 ${GREEN}Server is running at port ${port}:

    📄 ${GREEN}Routes are available at: ${routesPageURL}

    💻 ${GREEN}Internal: ${URL}
    🌎 ${GREEN}External: ${IP}
    ${RED}---------------------------------------
  `);
};

const generateStaticAssets = () => {
  let assetsArray = [];

  for (const asset in config.static) {
    const assetObject = config.static[asset];
    const srcPath = getAssetPath(SRC, assetObject.src);
    const destPath = getAssetPath(DEST, assetObject.dest ? assetObject.dest : assetObject.src);
    const assetFolderExist = existsSync(srcPath);

    if (assetFolderExist) {
      assetsArray.push({
        from: srcPath,
        to: destPath,
      });
    }
  }

  return assetsArray;
};

const pluginsConfiguration = {
  HTMLWebpackPlugin: {
    minify: false,
    inject: 'body',
    hash: isProduction && !config.externals ? config.cache_boost : false,
    scriptLoading: 'defer',
    cache: false,
    meta: {
      viewport: 'width=device-width, initial-scale=1, shrink-to-fit=no',
    },
    optimize: {
      prefetch: true,
    },
  },
  DevServer: {
    contentBase: posix.relative(__dirname, config.dest),
    hot: true,
    host: '0.0.0.0',
    compress: true,
    watchContentBase: true,
    disableHostCheck: true,
    historyApiFallback: true,
    liveReload: false,
    overlay: true,
    useLocalIp: true,
    noInfo: true,
    headers: {
      'Access-Control-Allow-Origin': '*',
    },
    clientLogLevel: 'silent',
    ...(config.server || {}),
    before(app, { options }) {
      const PORT = config.server.port || options.port;

      options.port = PORT;
      options.public = `localhost:${PORT}`;
    },
    after(app, server, compiler) {
      const files = [getAssetPath(SRC, config.templates.src), getAssetPath(SRC, config.scripts.src)];
      const { port } = server.options;

      chokidar.watch(files).on('change', () => {
        server.sockWrite(server.sockets, 'content-changed');
      });

      compiler.hooks.done.tap('show-server-settings', (stats) => {
        try {
          postServerMessage(port);
        } catch (error) {
          console.error(error);
        }
      });
    },
  },
  MiniCssExtract: {
    filename: getAssetName(config.styles.dest, '[name]', 'css'),
  },
  DefinePlugin: {
    'process.env': {
      NODE_ENV: JSON.stringify(ENV),
      ROUTES_PAGE: JSON.stringify(routesPage),
      ROUTES: JSON.stringify(getAllPagesExceptRoutes()),
    },
  },
  ProvidePlugin: {},
  StyleLint: {
    configFile: 'stylelint.config.js',
    context: getAssetPath(SRC, config.styles.src),
    syntax: config.styles.extension,
  },
  ESLint: {
    overrideConfigFile: 'eslintrc.js',
    extensions: ['.js'],
    files: join(config.src, config.scripts.src),
  },
  ErrorsPlugin: {
    clearConsole: true,
  },
  CopyPlugin: {
    patterns: generateStaticAssets(),
  },
  ImageMin: {
    cacheFolder: resolve(__dirname, 'node_modules/.cache'),
    disable: !isProduction,
    pngquant: {
      quality: 75,
    },
    plugins: [
      imageminMozjpeg({
        quality: 75,
        progressive: true,
      }),
    ],
  },
  ImageminWebp: {
    config: [
      {
        test: /\.(jpe?g|png)/,
        options: {
          quality: 75,
        },
      },
    ],
    overrideExtension: true,
    silent: true,
  },
  SVGSpriteMap: {
    output: {
      filename: 'images/svg-sprite.svg',
      svg: {
        // Disable `width` and `height` attributes on the root SVG element
        // as these will skew the sprites when using the <view> via fragment identifiers
        sizes: false
      }
    },
    sprite: {
      generate: {
        // Generate <use> tags within the spritemap as the <view> tag will use this
        use: true,

        // Generate <view> tags within the svg to use in css via fragment identifier url
        // and add -fragment suffix for the identifier to prevent naming collisions with the symbol identifier
        view: '-fragment',

        // Generate <symbol> tags within the SVG to use in HTML via <use> tag
        symbol: true
      },
    },
    // styles: {
    //   // Specify that we want to use URLs with fragment identifiers in a styles file as well
    //   format: 'fragment',
    //
    //   // Path to the styles file, note that this method uses the `output.publicPath` webpack option
    //   // to generate the path/URL to the spritemap itself so you might have to look into that
    //   filename: path.join(__dirname, 'src/scss/_sprites.scss')
    // }
  }
};

// creating new instance of plugin for each of the pages that we have
const generateHtmlPlugins = () => {
  const templateFiles = getAllPagesExceptRoutes();

  return templateFiles.map((item) => {
    // Split names and extension
    const parts = item.split('.');
    const name = parts[0];
    const template = getAssetPath(SRC, `${join(sitePages, name)}.${config.templates.extension}`);
    const filename = getAssetPath(DEST, `${join(config.templates.dest, name)}.html`);

    // Create new HTMLWebpackPlugin with options
    return new HTMLWebpackPlugin({
      title: basename(dirname(__dirname)),
      template,
      filename,
      excludeChunks: [routesPage],
      ...pluginsConfiguration.HTMLWebpackPlugin,
    });
  });
};

const htmlPlugins = () => {
  let plugins = generateHtmlPlugins();

  if (!isProduction) {
    plugins.push(
      new HTMLWebpackPlugin({
        title: basename(dirname(__dirname)),
        template: getAssetPath(SRC, `${sitePages}/${routesPage}.html`),
        filename: getAssetPath(DEST, `${config.templates.dest}/${routesPage}.html`),
        chunks: [routesPage],
        minify: false,
        scriptLoading: 'defer',
        meta: {
          viewport: 'width=device-width, initial-scale=1, shrink-to-fit=no',
        },
      })
    );
  }

  plugins.concat([
    new ScriptExtHtmlWebpackPlugin({
      defaultAttribute: 'defer',
    }),
  ]);

  return plugins;
};

const getPlugins = () => {
  let devPlugins = [new webpack.DefinePlugin(pluginsConfiguration.DefinePlugin)];
  let prodPlugins = [];

  let defaultPlugins = [
    new FixStyleOnlyEntriesPlugin({ silent: true }),
    new webpack.ProvidePlugin(pluginsConfiguration.ProvidePlugin),
    new ErrorsPlugin(pluginsConfiguration.ErrorsPlugin),
    new MiniCssExtractPlugin(pluginsConfiguration.MiniCssExtract),
    new WebpackNotifierPlugin({ excludeWarnings: true }),
    new ImageminPlugin(pluginsConfiguration.ImageMin),
  ];

  if (config.svgSprite) [
    defaultPlugins.push(new SVGSpritemapPlugin('src/images/icons/*.svg', pluginsConfiguration.SVGSpriteMap))
  ]

  if (config.webp) {
    defaultPlugins.push(new ImageminWebpWebpackPlugin(pluginsConfiguration.ImageminWebp));
  }

  if (generateStaticAssets().length) {
    defaultPlugins.push(new CopyWebpackPlugin(pluginsConfiguration.CopyPlugin));
  }

  if (!isProduction) {
    devPlugins.map((item) => defaultPlugins.push(item));
  }

  if (isProduction) {
    prodPlugins.map((item) => defaultPlugins.push(item));
  }

  // enable linters only if config.linters === true
  if (config.linters && config.linters.css) {
    defaultPlugins.push(new StyleLintPlugin(pluginsConfiguration.StyleLint));
  }

  if (config.linters && config.linters.js) {
    defaultPlugins.push(new ESLintPlugin(pluginsConfiguration.ESLint));
  }

  // add bundle analyze only if config.debug === true;
  if (isProduction && config.debug) {
    defaultPlugins.push(new BundleAnalyzerPlugin());
  }

  return defaultPlugins.concat(htmlPlugins());
};

const getTemplatesLoader = (templateType) => {
  const PUG = new RegExp('pug');
  const TWIG = new RegExp('twig');
  const viewsPath = join(config.src, config.templates.src);

  if (PUG.test(templateType)) {
    return {
      test: PUG,
      use: ['raw-loader', `pug-html-loader?basedir=${join(config.src, config.templates.src)}`],
    };
  }

  if (TWIG.test(templateType)) {
    return {
      test: TWIG,
      use: [
        'raw-loader',
        {
          loader: 'twig-html-loader',
          options: {
            data: (context) => {
              const data = resolve(__dirname, 'data.json');
              // going throught all twig files, including only _{helpers}
              const helpers = readdir.sync(getAssetPath(SRC, sitePages), {
                deep: true,
                filter: (stats) => stats.isFile() && stats.path.indexOf('_') !== -1,
              });

              helpers.forEach((file) => {
                // pushing helper file to context and force plugin to rebuild templates on helpers changes
                // fixing issue, when path inside helpers was changed, but compiler didn't noticed about those changes to the path
                context.addDependency(join(config.src, config.templates.src, file));
              });

              context.addDependency(data); // Force webpack to watch file
              return context.fs.readJsonSync(data, { throws: false }) || {};
            },
            namespaces: {
              layout: resolve(__dirname, join(viewsPath, '_layout')),
              components: resolve(__dirname, join(viewsPath, '_components')),
              includes: resolve(__dirname, join(viewsPath, '_includes')),
            },
          },
        },
      ],
    };
  }

  return {};
};

const getScriptsLoader = (templateType) => {
  const TS = new RegExp('ts');

  if (TS.test(templateType)) {
    return {
      // /node_modules\/(?!(module_to_include)\/).*/
      test: /\.tsx?$/,
      exclude: /node_modules/,
      loaders: ['awesome-typescript-loader'],
    };
  }

  return {
    test: /\.m?js$/,
    exclude: /node_modules/,
    loaders: ['babel-loader'],
  };
};

const getStaticAssetOutputPath = ({ assets, outputFolder, parsedUrlPath, stylesDest }) => {
  const { src } = assets;
  const destination = posix.relative(stylesDest, outputFolder);
  const source = posix.join(config.src, src);
  const resultPath = parsedUrlPath.dir.replace(source, destination);

  parsedUrlPath.dir = resultPath;

  return posix.format(parsedUrlPath);
};

const getModules = () => {
  const modules = {
    rules: [
      {
        test: /\.(sa|sc|c)ss$/,
        use: [
          MiniCssExtractPlugin.loader,
          'css-loader',
          {
            loader: 'postcss-loader',
            options: {
              postcssOptions: {
                plugins: {
                  cssnano: config.minimizeCSS && isProduction ? {} : false,
                  perfectionist:
                    config.minimizeCSS && isProduction
                      ? false
                      : {
                        cascade: false,
                        colorShorthand: false,
                        indentSize: 2,
                        maxSelectorLength: false,
                        maxAtRuleLength: false,
                        maxValueLength: false,
                      },
                },
                config: true,
              },
            },
          },
          'group-css-media-queries-loader',
          'sass-loader',
        ],
      },
      {
        test: /\.(woff(2)?|eot|ttf|otf|png|jpe?g|gif|svg)$/,
        use: [
          {
            loader: 'file-loader',
            options: {
              name: '[path][name].[ext][query]',
              emitFile: false,
              publicPath: function (url) {
                const { dest } = config.styles;
                const parsedPath = parse(url);
                const isFonts = url.includes(config.static.fonts.src);
                const isImages = url.includes(config.static.images.src);
                const fontsOutput = config.static.fonts.dest ? config.static.fonts.dest : config.static.fonts.src;
                const imagesOutput = config.static.images.dest ? config.static.images.dest : config.static.images.src;

                if (isFonts) {
                  return getStaticAssetOutputPath({
                    assets: config.static.fonts,
                    outputFolder: fontsOutput,
                    parsedUrlPath: parsedPath,
                    stylesDest: dest,
                  });
                } else if (isImages) {
                  return getStaticAssetOutputPath({
                    assets: config.static.images,
                    outputFolder: imagesOutput,
                    parsedUrlPath: parsedPath,
                    stylesDest: dest,
                  });
                } else {
                  return url;
                }
              },
            },
          },
        ],
      },
    ],
  };

  modules.rules.unshift(getScriptsLoader(config.scripts.extension), getTemplatesLoader(config.templates.extension));

  return modules;
};

const getOptimization = () => {
  if (!isProduction) return {};
  const cacheGroupName = 'vendors';
  const shouldBoost = config.cache_boost && !config.externals;

  const settings = {
    boost: {
      namedModules: true,
      namedChunks: true,
      moduleIds: 'named',
      chunkIds: 'named',
      runtimeChunk: 'single',
      splitChunks: {
        cacheGroups: {
          [cacheGroupName]: {
            chunks: 'all',
            test: /node_modules/,
          },
        },
      },
    },
    default: {
      namedModules: false,
      namedChunks: false,
      moduleIds: false,
      chunkIds: false,
      runtimeChunk: false,
    },
  };

  const settingsType = shouldBoost ? 'boost' : 'default';

  return {
    ...settings[settingsType],
    minimize: config.minimizeJS,
    minimizer: [
      new TerserPlugin({
        exclude: !config.minimizeJS ? join(config.scripts.src, config.scripts.bundle) : undefined,
        extractComments: false,
        terserOptions: {
          cache: true,
          parallel: true,
          compress: {
            inline: false,
            warnings: false,
            drop_console: true,
          },
          output: {
            comments: false,
          },
        },
      }),
    ],
  };
};

/*
    External entries, specified in config.json file as {externals}. Could be useful, if we need separate CSS file for frameworks like Bootstrap etc.
    Usage in config:

    "externals": {
      "bootstrap": "styles/bootstrap.scss",
      "test": "js/test.js"
    }

    Where [filename] = [key], e.g. "bootstrap": ... => "bootstrap.css"

    This will generate additional CSS file and additional JS file, also - they will be automatically included into the generated HTML page.
*/
const addExternalEntries = (entries) => {
  const EXTERNAL_POSITIONS = {
    before: 'beforeBundle',
    after: 'afterBundle',
    error: 'Order should be "beforeBundle" or "afterBundle" only',
  };
  for (const external in config.externals) {
    const targetBundle = config.externals[external];
    // externals inclusion order, afterBundle - add after main bundles, beforeBundle - add before main bundles
    const order = config.externals.order || EXTERNAL_POSITIONS.before;

    if (typeof targetBundle === 'object') {
      const bundles = targetBundle.map((bundle) => {
        const externalBundle = resolve(__dirname, config.src, bundle);
        const pathExcludeSrc = bundle.replace(`${config.src}/`, '');

        if (existsSync(externalBundle)) {
          return externalBundle;
        }
        return console.error(
          `Path to externals should not include ${config.src}/, webpack resolve paths to this folder automatically. \nPlease change path to the following: ${pathExcludeSrc}`
        );
      });

      if (order === EXTERNAL_POSITIONS.before) {
        entries = {
          [external]: bundles,
          ...entries,
        };
      } else if (order === EXTERNAL_POSITIONS.after) {
        entries = {
          ...entries,
          [external]: bundles,
        };
      } else {
        throw new Error(EXTERNAL_POSITIONS.error);
      }
    } else if (typeof targetBundle === 'string') {
      const externalBundle = resolve(__dirname, config.src, targetBundle);

      if (existsSync(externalBundle)) {
        if (order === EXTERNAL_POSITIONS.before) {
          entries = {
            [external]: externalBundle,
            ...entries,
          };
        } else if (order === EXTERNAL_POSITIONS.after) {
          entries = {
            ...entries,
            [external]: externalBundle,
          };
        } else {
          throw new Error(EXTERNAL_POSITIONS.error);
        }
      }
    } else {
      console.error('Externals property should be a String or Array of strings, e.g. bootstrap: "bundle/path" or bootstrap: ["path/to/scss", "path/to/js"]');
    }
  }

  return entries;
};

const getEntries = () => {
  // Need this since useBuildins: usage in babel didn't add polyfill for Promise.all() when webpack is bundling
  // const iterator = ['core-js/modules/es.array.iterator', 'regenerator-runtime/runtime'];
  const iterator = [];
  let entries = {};
  const routesPageEntry = posix.resolve(join(config.src, config.scripts.src, 'utils', `${routesPage}.js`));

  if (config.scripts) {
    // default JS entry {app.js} - used for all pages, if no specific entry is provided
    const entryJsFile = join(config.scripts.src, `${config.scripts.bundle}.${config.scripts.extension}`);
    const entry = iterator.concat([getAssetPath(SRC, entryJsFile)]);

    if (!config.scripts.static) {
      entries[config.scripts.bundle] = [...entry];
    }
  }

  if (config.styles) {
    // default CSS entry {main.scss} - used for all pages, if no specific entry is provided
    const entryCSSFile = join(config.styles.src, `${config.styles.bundle}.${config.styles.extension}`);
    const styleAsset = getAssetPath(SRC, entryCSSFile);

    if (entries[config.styles.bundle]) {
      entries[config.styles.bundle].push(styleAsset);
    } else {
      entries[config.styles.bundle] = [styleAsset];
    }
  }

  if (!isProduction) {
    entries[routesPage] = routesPageEntry;
  }

  if (config.externals) entries = addExternalEntries(entries);

  return entries;
};

const webpackConfig = {
  mode: ENV,
  entry: getEntries(),
  devtool: isProduction ? false : 'source-map',
  stats: isProduction,
  externals: {
    jquery: 'jQuery',
  },
  output: {
    publicPath: PUBLIC_PATH,
    path: posix.resolve(config.dest),
    filename: getAssetName(config.scripts.dest, '[name]', 'js'),
    crossOriginLoading: 'anonymous',
  },
  plugins: getPlugins(),
  resolve: {
    mainFiles: ['index'],
    extensions: [`.${config.scripts.extension}`],
    alias: {
      JS: getAssetPath(SRC, config.scripts.src),
      Utils: getAssetPath(SRC, `${config.scripts.src}/utils`),
      Vendors: getAssetPath(SRC, `${config.scripts.src}/vendors`),
      Plugins: getAssetPath(SRC, `${config.scripts.src}/plugins`),
      Components: getAssetPath(SRC, `${config.scripts.src}/components`),
      Animations: getAssetPath(SRC, `${config.scripts.src}/animations`),
    },
  },
  optimization: {
    usedExports: true,
    ...getOptimization(),
  },
  module: getModules(),
  devServer: pluginsConfiguration.DevServer,
};

module.exports = webpackConfig;
