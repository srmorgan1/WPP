# WPP Management React Frontend

This is the React frontend for the WPP Management application.

## Getting Started

### Prerequisites

- Node.js 16+ 
- npm or yarn

### Installation

1. Install dependencies:
```bash
npm install
```

2. Start the development server:
```bash
npm start
```

The app will be available at http://localhost:3000

### Building for Production

```bash
npm run build
```

This creates a `build/` directory with optimized production files.

## Features

- **Dashboard**: System status overview and quick actions
- **Database Management**: Update database with real-time progress tracking
- **Report Generation**: Create reports with date selection
- **Real-time Updates**: WebSocket integration for live progress updates
- **Data Visualization**: Interactive tables for Excel data and logs
- **Responsive Design**: Works on desktop and mobile devices

## API Integration

The frontend communicates with the FastAPI backend at:
- API: `http://localhost:8000`
- WebSocket: `ws://localhost:8000/ws`

## Project Structure

```
src/
├── components/          # Reusable UI components
│   ├── DataTable.js    # Excel data display
│   ├── LogViewer.js    # Log content viewer
│   ├── ProgressBar.js  # Progress indicator
│   └── StatusIndicator.js # Status badges
├── pages/              # Page components
│   ├── Dashboard.js    # Main dashboard
│   ├── DatabasePage.js # Database management
│   └── ReportsPage.js  # Report generation
├── services/           # API and WebSocket services
│   └── api.js         # API client and WebSocket
├── App.js             # Main app component
└── index.js           # App entry point
```

## Technologies Used

- **React 18**: UI framework
- **React Router**: Navigation
- **Tailwind CSS**: Styling
- **Axios**: HTTP client
- **Lucide React**: Icons
- **WebSocket API**: Real-time updates