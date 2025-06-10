import React, { useEffect, useState } from 'react';
import { AgGridReact } from 'ag-grid-react';
import 'ag-grid-community/styles/ag-grid.css';
import 'ag-grid-community/styles/ag-theme-alpine.css';
import axios from 'axios';

const TaskTable = ({ userId }) => {
  const [rowData, setRowData] = useState([]);

  const columnDefs = [
    { headerName: 'Job ID', field: 'job_id', sortable: true, filter: true },
    { headerName: 'Type', field: 'metadata.job_prefix', sortable: true, filter: true },
    { headerName: 'Status', field: 'status', sortable: true, filter: true },
    { headerName: 'Next Run', field: 'next_run', sortable: true, filter: true },
  ];

  useEffect(() => {
    if (userId) {
      axios.get(`http://localhost:8001/users/${userId}/jobs`).then(response => {
        setRowData(response.data.jobs);
      }).catch(error => console.error('Error fetching jobs:', error));
    }
  }, [userId]);

  return (
    <div className="ag-theme-alpine" style={{ height: '400px', width: '100%' }}>
      <AgGridReact
        columnDefs={columnDefs}
        rowData={rowData}
        pagination={true}
        paginationPageSize={10}
      />
    </div>
  );
};

export default TaskTable;