import React, { useEffect, useState } from 'react';
import { Timeline } from 'vis-timeline/standalone';
import axios from 'axios';

const TaskTimeline = ({ userId }) => {
  const [tasks, setTasks] = useState([]);

  useEffect(() => {
    if (userId) {
      axios.get(`http://localhost:8001/users/${userId}/jobs`).then(response => {
        const items = response.data.jobs.map(job => ({
          id: job.job_id,
          content: job.metadata.job_prefix,
          start: job.next_run,
        }));
        setTasks(items);
      }).catch(error => console.error('Error fetching jobs:', error));
    }
  }, [userId]);

  useEffect(() => {
    if (tasks.length > 0) {
      const container = document.getElementById('timeline');
      new Timeline(container, tasks, { height: '200px' });
    }
  }, [tasks]);

  return <div id="timeline" />;
};

export default TaskTimeline;