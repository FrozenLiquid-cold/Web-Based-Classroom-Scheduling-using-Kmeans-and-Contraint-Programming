const TIME_BLOCKS = [
	{ label: '7:30–8:00' }, { label: '8:00–8:30' }, { label: '8:30–9:00' },
	{ label: '9:00–9:30' }, { label: '9:30–10:00' }, { label: '10:00–10:30' },
	{ label: '10:30–11:00' }, { label: '11:00–11:30' }, { label: '11:30–12:00' },
	{ label: '13:00–13:30' }, { label: '13:30–14:00' }, { label: '14:00–14:30' },
	{ label: '14:30–15:00' }, { label: '15:00–15:30' }, { label: '15:30–16:00' },
	{ label: '16:00–16:30' }, { label: '16:30–17:00' }, { label: '17:00–17:30' },
	{ label: '17:30–18:00' }, { label: '18:00–18:30' }, { label: '18:30–19:00' },
	{ label: '19:00–19:30' }, { label: '19:30–20:00' },
  ];
  
  export function getTimeBlocks() {
	return TIME_BLOCKS;
  }
  
  export function generateSchedule({ subjects, instructors, rooms, days }) {
	const schedule = [];
	const used = new Set(); // `${day}-${slot}-${room}` and `${day}-${slot}-${inst}`
  
	let instructorIdx = 0;
	let roomIdx = 0;
  
	for (const subject of subjects) {
	  let placed = false;
	  const subjectType = subject.type?.toUpperCase() || 'LEC';
	  const candidates = rooms.filter(r => r.type === subjectType);
	  const availableRooms = candidates.length ? candidates : rooms;
  
	  // Shuffle slightly to distribute load evenly
	  const randomDay = days[Math.floor(Math.random() * days.length)];
	  for (let t = 0; t < TIME_BLOCKS.length; t++) {
		const room = availableRooms[roomIdx % availableRooms.length];
		const inst = instructors[instructorIdx % instructors.length];
		const roomKey = `${randomDay.id}-${t}-${room.id}`;
		const instKey = `${randomDay.id}-${t}-${inst.id}`;
  
		if (!used.has(roomKey) && !used.has(instKey)) {
		  used.add(roomKey);
		  used.add(instKey);
		  schedule.push({
			subjectId: subject.id,
			dayId: randomDay.id,
			time: TIME_BLOCKS[t].label,
			roomId: room.id,
			instructorId: inst.id,
		  });
		  placed = true;
		  break;
		}
  
		instructorIdx++;
		roomIdx++;
	  }
  
	  if (!placed) {
		schedule.push({
		  subjectId: subject.id,
		  dayId: null,
		  time: null,
		  roomId: null,
		  instructorId: null,
		});
	  }
	}
  
	return schedule;
  }
  