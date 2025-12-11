import { defineConfig, loadEnv } from 'vite'
import react from '@vitejs/plugin-react'
import path from 'path'

// https://vitejs.dev/config/
export default defineConfig(({ mode }) => {
  // Load environment variables based on mode (development, production, etc.)
  const env = loadEnv(mode, process.cwd(), '')
  
  return {
    plugins: [
      react({
        // Enable Fast Refresh for better development experience
        fastRefresh: true,
      }),
    ],
    
    resolve: {
      alias: {
        '@': path.resolve(__dirname, './src'),
      },
    },
    
    // Environment variable configuration
    define: {
      // Expose environment variables to the app
      // Vite automatically exposes VITE_* variables, but we can add validation here
      __APP_VERSION__: JSON.stringify(process.env.npm_package_version || '0.0.0'),
    },
    
    // Build optimizations
    build: {
      // Output directory
      outDir: 'dist',
      
      // Generate source maps for debugging
      // 'hidden' generates source maps but doesn't reference them in the bundle
      // Use 'true' for development builds, 'hidden' for production
      sourcemap: mode === 'production' ? 'hidden' : true,
      
      // Target modern browsers for smaller bundle size
      target: 'esnext',
      
      // Minification options
      minify: 'esbuild',
      
      // Chunk size warning limit (500kb)
      chunkSizeWarningLimit: 500,
      
      // Rollup options for advanced bundling
      rollupOptions: {
        output: {
          // Manual chunk splitting for better caching
          // IMPORTANT: Order matters - React must be in its own chunk and load first
          manualChunks: {
            // React core - must be separate and load first
            'react-vendor': ['react', 'react-dom', 'react/jsx-runtime'],
            
            // Cognito SDK - authentication library
            'aws-vendor': ['amazon-cognito-identity-js'],
            
            // Icons - separate for better caching
            'icons-vendor': ['lucide-react'],
          },
          
          // Asset file naming
          assetFileNames: (assetInfo) => {
            const info = assetInfo.name?.split('.') || [];
            const ext = info[info.length - 1];
            
            if (/png|jpe?g|svg|gif|tiff|bmp|ico/i.test(ext)) {
              return `assets/images/[name]-[hash][extname]`;
            } else if (/woff|woff2|eot|ttf|otf/i.test(ext)) {
              return `assets/fonts/[name]-[hash][extname]`;
            }
            return `assets/[name]-[hash][extname]`;
          },
          
          // Chunk file naming
          chunkFileNames: 'assets/js/[name]-[hash].js',
          
          // Entry file naming
          entryFileNames: 'assets/js/[name]-[hash].js',
        },
      },
      
      // CSS code splitting
      cssCodeSplit: true,
      
      // Report compressed size (can be disabled for faster builds)
      reportCompressedSize: true,
      
      // Common chunk options
      commonjsOptions: {
        transformMixedEsModules: true,
      },
    },
    
    // Development server configuration
    server: {
      port: 3000,
      strictPort: false,
      host: true,
      open: false,
      
      // CORS configuration for development
      cors: true,
      
      // HMR configuration
      hmr: {
        overlay: true,
      },
    },
    
    // Preview server configuration
    preview: {
      port: 4173,
      strictPort: false,
      host: true,
      open: false,
    },
    
    // Dependency optimization
    optimizeDeps: {
      include: [
        'react',
        'react-dom',
        'amazon-cognito-identity-js',
        'uuid',
      ],
      exclude: [],
    },
    
    // Performance optimizations
    esbuild: {
      // Drop console and debugger in production
      drop: mode === 'production' ? ['console', 'debugger'] : [],
      
      // Legal comments handling
      legalComments: 'none',
    },
  }
})
