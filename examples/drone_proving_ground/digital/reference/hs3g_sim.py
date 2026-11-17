"""HS-3G-B forces and a simulation-only controller around native PyBullet.

PyBullet integrates the six-DOF rigid body; no aircraft state is animated or
reset to its target. Position PID uses an SO(3) attitude-error PD inner loop.
This is deliberately not INAV firmware, SITL or a sensor-calibrated twin.
"""
from __future__ import annotations

import math
from pathlib import Path

import numpy as np


def smooth(a, b, t, start, end):
    u = np.clip((t-start)/(end-start), 0, 1)
    s = 10*u**3 - 15*u**4 + 6*u**5
    v = (30*u**2-60*u**3+30*u**4)/(end-start)
    return np.array(a)+(np.array(b)-a)*s, (np.array(b)-a)*v


def setpoint(t, floor):
    start = np.array([0., 0., floor+0.0005])
    hover = np.array([0., 0., .65])
    zero = np.zeros(3)
    yaw = 0.
    if t < 3:
        position, velocity = smooth(start, hover, t, 0, 3); phase = 'takeoff'
    elif t < 5:
        position, velocity, phase = hover, zero, 'hover'
    elif t < 13:
        corners = [hover, [.45,0,.65], [.45,.45,.65], [0,.45,.65], hover]
        leg = min(3, int((t-5)/2))
        position, velocity = smooth(corners[leg], corners[leg+1], t, 5+leg*2, 7+leg*2)
        phase = 'square'
    elif t < 22:
        position, velocity = hover, zero
        if t < 16:
            yaw = float(smooth(0., math.pi/2, t, 13, 16)[0]); phase = 'yaw'
        elif t < 18:
            yaw, phase = math.pi/2, 'gust'
        elif t < 21:
            yaw, phase = math.pi/2, 'recover'
        else:
            yaw = float(smooth(math.pi/2, 0., t, 21, 22)[0]); phase = 'yaw_return'
    else:
        position, velocity = smooth(hover, [0,0,floor+0.0001], t, 22, 26)
        phase = 'land' if t < 26.5 else 'landed'
    return position, velocity, yaw, phase


class MotorTable:
    def __init__(self, table, config):
        rows = np.array(table['props']['GF3028-3'])
        names = table['columns']
        self.rpm_table = rows[:,names.index('rpm')]
        self.thrust_table = rows[:,names.index('thrust_g')] * config['gravity_m_s2'] / 1000
        self.current_table = rows[:,names.index('current_a')]
        self.max_rpm = float(self.rpm_table[-1])

    def force_at_rpm(self, rpm):
        low = self.thrust_table[0] * (rpm/self.rpm_table[0])**2
        return np.where(rpm < self.rpm_table[0], low, np.interp(rpm, self.rpm_table, self.thrust_table))

    def rpm_at_force(self, force):
        low = self.rpm_table[0] * np.sqrt(np.maximum(0, force)/self.thrust_table[0])
        return np.clip(np.where(force < self.thrust_table[0], low, np.interp(force, self.thrust_table, self.rpm_table)), 0, self.max_rpm)

    def current_at_rpm(self, rpm):
        low = self.current_table[0] * (rpm/self.rpm_table[0])**3
        return np.where(rpm < self.rpm_table[0], low, np.interp(rpm, self.rpm_table, self.current_table))


class Battery:
    """Assumed OCV/sag model; table current is the sole motor-current model."""
    def __init__(self, config, motor):
        self.parameters = config['battery']
        self.motor = motor
        self.soc = self.parameters['initial_soc']['value']
        self.consumed_mah = 0.

    def load(self, requested_rpm):
        if self.soc <= 0:
            return 0., 0., np.zeros_like(requested_rpm)
        b = self.parameters
        curve = np.array(b['ocv_curve_soc_cell_v']['value'])
        ocv = float(np.interp(self.soc, curve[:,0], curve[:,1])) * b['cells']['value']
        resistance = b['internal_resistance_ohm']['value']
        power = b['avionics_power_w']['value']
        bench = b['bench_voltage_v']['value']

        def electrical(voltage):
            rpms = np.clip(requested_rpm, 0, self.motor.max_rpm * voltage / bench)
            motor_current = float(np.sum(self.motor.current_at_rpm(rpms)))
            available = ocv - resistance * motor_current
            # High-voltage root of V = OCV - R*(I_motor + P_avionics/V).
            discriminant = available**2 - 4*resistance*power
            terminal = (available + math.sqrt(discriminant))/2 if discriminant >= 0 and available > 0 else 0.
            return terminal, rpms, motor_current

        voltage, rpms, motor_current = electrical(ocv)
        if np.any(rpms > self.motor.max_rpm * voltage / bench):
            low, high = 0., ocv
            for _ in range(48):
                voltage = (low+high)/2
                if electrical(voltage)[0] > voltage:
                    low = voltage
                else:
                    high = voltage
            voltage = (low+high)/2
            _, rpms, motor_current = electrical(voltage)
        if voltage <= 0:
            return 0., 0., np.zeros_like(requested_rpm)
        current = motor_current + power / voltage
        return voltage, current, rpms

    def advance(self, current, dt):
        self.consumed_mah = min(self.parameters['capacity_mah']['value'] * self.parameters['initial_soc']['value'],
                                self.consumed_mah + current * dt / 3.6)
        self.soc = max(0., self.parameters['initial_soc']['value'] -
                       self.consumed_mah / self.parameters['capacity_mah']['value'])


class World(MotorTable):
    def __init__(self, model, table, config, scenario):
        import pybullet as p
        self.p = p
        self.client = p.connect(p.DIRECT)
        self.model, self.cfg, self.scenario = model, config, scenario
        self.dt = 1 / config['physics_hz']
        self.nominal_mass = model['mass_kg']
        self.mass = self.nominal_mass + scenario.get('extra_mass_g', 0) / 1000
        self.cg = np.array(model['centre_of_mass_m'])
        self.rotors = np.array(model['rotor_centres_m']) - self.cg
        self.J = np.array(model['dynamics_inertia_diagonal_kg_m2'])
        self.spin = np.array(model['rotor_spin_signs'])
        a = config['assumptions']
        self.allocation = np.stack([np.ones(4), self.rotors[:,1], -self.rotors[:,0], self.spin*a['yaw_torque_per_thrust_m']])
        self.inverse_allocation = np.linalg.inv(self.allocation)
        super().__init__(table, config)
        self.battery = Battery(config, self)
        self.integral = np.zeros(3)
        self.rpms, self.rpm_command = np.zeros(4), np.zeros(4)
        self.landed = self.fault_detected = False
        p.setGravity(0, 0, -config['gravity_m_s2'], physicsClientId=self.client)
        p.setTimeStep(self.dt, physicsClientId=self.client)
        p.setPhysicsEngineParameter(numSolverIterations=80, deterministicOverlappingPairs=1, physicsClientId=self.client)
        plane = p.createCollisionShape(p.GEOM_PLANE, physicsClientId=self.client)
        plane_body = p.createMultiBody(0, plane, physicsClientId=self.client)
        p.changeVisualShape(plane_body, -1, rgbaColor=[0,0,0,0], physicsClientId=self.client)
        lo, hi = np.array(model['bounds_m']) - self.cg
        centre, half = (lo+hi)/2, (hi-lo)/2
        self.floor = float(-lo[2])
        collision = p.createCollisionShape(p.GEOM_BOX, halfExtents=half.tolist(), collisionFramePosition=centre.tolist(), physicsClientId=self.client)
        self.body = p.createMultiBody(self.mass, collision, basePosition=[0,0,self.floor+.0005], physicsClientId=self.client)
        # The collision envelope is not part of the visible CAD assembly.
        p.changeVisualShape(self.body, -1, rgbaColor=[0,0,0,0], physicsClientId=self.client)
        p.changeDynamics(self.body, -1, localInertiaDiagonal=(self.J * self.mass/self.nominal_mass).tolist(),
                         linearDamping=0, angularDamping=0, lateralFriction=.7, restitution=0, physicsClientId=self.client)
        self.visual_bodies = []
        self.tick = 0

    def state(self):
        p = self.p
        position, quaternion = p.getBasePositionAndOrientation(self.body, physicsClientId=self.client)
        velocity, omega = p.getBaseVelocity(self.body, physicsClientId=self.client)
        R = np.array(p.getMatrixFromQuaternion(quaternion)).reshape(3,3)
        return np.array(position), np.array(quaternion), np.array(velocity), np.array(omega), R

    def control(self, pos, vel, omega, R, target, target_vel, yaw):
        a = self.cfg['assumptions']
        self.integral = np.clip(self.integral + (target-pos) / self.cfg['control_hz'], -.5, .5)
        acc = np.array(a['position_kp'])*(target-pos) + np.array(a['position_kd'])*(target_vel-vel) + np.array(a['position_ki'])*self.integral
        norm = np.linalg.norm(acc[:2])
        acc[:2] *= min(1., a['max_horizontal_acceleration_m_s2']/max(norm, 1e-10))
        acc[2] = np.clip(acc[2], -5, 5) + self.cfg['gravity_m_s2']
        desired_z = acc / np.linalg.norm(acc)
        heading = np.array([math.cos(yaw), math.sin(yaw), 0])
        desired_y = np.cross(desired_z, heading); desired_y /= np.linalg.norm(desired_y)
        desired_R = np.column_stack([np.cross(desired_y, desired_z), desired_y, desired_z])
        skew = (desired_R.T @ R - R.T @ desired_R) / 2
        error_R = np.array([skew[2,1], skew[0,2], skew[1,0]])
        body_omega = R.T @ omega
        w = a['attitude_frequency_rad_s']; damping = a['attitude_damping_ratio']
        torque = -self.J*w*w*error_R - self.J*(2*damping*w)*body_omega + np.cross(body_omega, self.J*body_omega)
        collective = max(0, float(self.nominal_mass*np.dot(acc, R[:,2])))
        forces = self.inverse_allocation @ np.r_[collective, torque]
        return self.rpm_at_force(np.clip(forces, 0, self.thrust_table[-1]))

    def step(self):
        p = self.p
        t = self.tick * self.dt
        pos, quat, vel, omega, R = self.state()
        target, target_vel, yaw, phase = setpoint(t, self.floor)
        fault = self.scenario.get('motor_failure')
        tilt = math.acos(float(np.clip(R[2,2], -1, 1)))
        if fault and t >= fault['at_s']+.3 and (tilt > math.radians(60) or np.linalg.norm(target-pos) > .45):
            self.fault_detected = True
        if self.tick % (self.cfg['physics_hz']//self.cfg['control_hz']) == 0:
            self.rpm_command = self.control(pos, vel, omega, R, target, target_vel, yaw)
        if phase == 'landed' or self.landed or self.fault_detected:
            self.rpm_command[:] = 0
        a = self.cfg['assumptions']
        self.rpms += (self.rpm_command-self.rpms)*(1-math.exp(-self.dt/a['motor_time_constant_s']))
        if fault and t >= fault['at_s']:
            self.rpms[fault['index']] = 0
        voltage, current, self.rpms = self.battery.load(self.rpms)
        self.battery.advance(current, self.dt)
        thrust = self.force_at_rpm(self.rpms)
        for rotor, force in zip(self.rotors, thrust):
            # Force point and direction are in the body's COM-centred local frame.
            p.applyExternalForce(self.body, -1, [0,0,float(force)], rotor.tolist(), p.LINK_FRAME, physicsClientId=self.client)
        yaw_torque = float(np.dot(self.spin, thrust)*a['yaw_torque_per_thrust_m'])
        p.applyExternalTorque(self.body, -1, [0,0,yaw_torque], p.LINK_FRAME, physicsClientId=self.client)
        wind = np.array(a['gust_force_n']) if a['gust_interval_s'][0] <= t < a['gust_interval_s'][1] else np.zeros(3)
        drag = -a['linear_drag_n_per_m_s']*vel
        external = wind+drag
        p.applyExternalForce(self.body, -1, external.tolist(), pos.tolist(), p.WORLD_FRAME, physicsClientId=self.client)
        total_force = R[:,2]*sum(thrust) + external - np.array([0,0,self.mass*self.cfg['gravity_m_s2']])
        p.stepSimulation(physicsClientId=self.client)
        self.tick += 1
        newpos, quat, newvel, omega, R = self.state()
        contact = bool(p.getContactPoints(bodyA=self.body, physicsClientId=self.client))
        if t > 25 and contact and abs(newvel[2]) < .08:
            self.landed = True
        rpy = p.getEulerFromQuaternion(quat)
        row = {'t_s': self.tick*self.dt, 'phase': 'failure_detected' if self.fault_detected else 'landed' if self.landed else phase,
               **{f'{k}_{axis}': float(value) for k, values in [('pos_m',newpos),('vel_m_s',newvel),('target_m',target),('force_n',total_force)] for axis,value in zip('xyz',values)},
               **{f'quat_{axis}': float(value) for axis,value in zip('xyzw',quat)},
               **{f'{k}_rad': float(value) for k,value in zip(['roll','pitch','yaw'],rpy)},
               **{f'rpm_{i+1}': float(value) for i,value in enumerate(self.rpms)},
               'current_a_est': current, 'terminal_voltage_v': voltage,
               'battery_soc': self.battery.soc, 'consumed_mah_est': self.battery.consumed_mah,
               'full_throttle_thrust_n_est': float(4*self.force_at_rpm(self.max_rpm*voltage/self.cfg['battery']['bench_voltage_v']['value'])),
               'tilt_deg': math.degrees(math.acos(float(np.clip(R[2,2],-1,1)))),
               'contact': int(contact), 'target_yaw_rad': yaw, 'fault_detected': int(self.fault_detected)}
        return row

    def prepare_visuals(self):
        p = self.p
        ground = p.createVisualShape(p.GEOM_BOX, halfExtents=[1.5,1.5,.004], rgbaColor=[.80,.84,.88,1], physicsClientId=self.client)
        p.createMultiBody(0, baseVisualShapeIndex=ground, basePosition=[0,0,-.004], physicsClientId=self.client)
        for xy in np.arange(-1.25, 1.26, .25):
            for axis in [0,1]:
                half = [.001,1.5,.0002] if axis == 0 else [1.5,.001,.0002]
                centre = [xy,0,.0002] if axis == 0 else [0,xy,.0002]
                visual = p.createVisualShape(p.GEOM_BOX, halfExtents=half, rgbaColor=[.58,.65,.72,1], physicsClientId=self.client)
                p.createMultiBody(0, baseVisualShapeIndex=visual, basePosition=centre, physicsClientId=self.client)
        for item in self.model['parts']:
            vertices = np.array(item['vertices_m'])-self.cg
            visual = p.createVisualShape(p.GEOM_MESH, vertices=vertices.tolist(), indices=np.array(item['faces']).ravel().tolist(),
                                         rgbaColor=item['colour'], physicsClientId=self.client)
            body = p.createMultiBody(0, baseVisualShapeIndex=visual, physicsClientId=self.client)
            self.visual_bodies.append((body, item))

    def camera(self, *, assembly=False, exploded=False, recorded=None, angles=None):
        from PIL import Image
        p = self.p
        if not self.visual_bodies:
            self.prepare_visuals()
        pos, quat, _, _, R = self.state()
        if recorded is not None:
            pos = np.array([recorded['pos_m_'+a] for a in 'xyz'])
            quat = [recorded['quat_'+a] for a in 'xyzw']
            R = np.array(p.getMatrixFromQuaternion(quat)).reshape(3,3)
        if assembly:
            pos = np.array([0.,0.,.10 if exploded else .065]); quat = [0,0,0,1]; R = np.eye(3)
        for body, item in self.visual_bodies:
            offset = np.array(item['explode_m']) if exploded else np.zeros(3)
            visual_pos, visual_quat = pos+R@offset, quat
            if not assembly and angles is not None and item['rotor_index'] is not None:
                index = item['rotor_index']; angle = float(angles[index])
                rotor_q = p.getQuaternionFromEuler([0,0,angle])
                rotor_R = np.array(p.getMatrixFromQuaternion(rotor_q)).reshape(3,3)
                visual_pos += R@(self.rotors[index]-rotor_R@self.rotors[index])
                visual_quat = p.multiplyTransforms([0,0,0],quat,[0,0,0],rotor_q)[1]
            # These are massless, non-colliding visualization objects only.
            p.resetBasePositionAndOrientation(body, visual_pos.tolist(), visual_quat, physicsClientId=self.client)
        camera = self.cfg['camera']
        target = pos if assembly else camera['target_m']
        view = p.computeViewMatrixFromYawPitchRoll(target, .40 if assembly else camera['distance_m'],
            40 if assembly else camera['yaw_deg'], -30 if assembly else camera['pitch_deg'], 0, 2)
        width,height = (720,480) if assembly else (camera['width_px'],camera['height_px'])
        projection = p.computeProjectionMatrixFOV(45 if assembly else camera['fov_deg'], width/height, .01, 8)
        _,_,rgba,_,_ = p.getCameraImage(width,height,viewMatrix=view,projectionMatrix=projection,renderer=p.ER_TINY_RENDERER,
                                       shadow=0,lightDirection=[-1,-2,3], physicsClientId=self.client)
        return Image.fromarray(np.asarray(rgba,dtype=np.uint8).reshape(height,width,4)[:,:,:3])

    def close(self):
        if self.p.isConnected(self.client):
            self.p.disconnect(self.client)


def run(model, table, config, scenario, out: Path, *, render=False):
    import csv
    from PIL import ImageDraw
    world = World(model, table, config, scenario)
    rows, frames = [], []
    try:
        for tick in range(round(scenario.get('duration_s',config['duration_s'])*config['physics_hz'])):
            row = world.step(); rows.append(row)
        with (out / (scenario['id'] + '.csv')).open('w',newline='') as handle:
            writer = csv.DictWriter(handle,fieldnames=list(rows[0]));writer.writeheader();writer.writerows(rows)
        if render:
            world.camera(assembly=True).save(out / 'ASSEMBLY.png')
            world.camera(assembly=True, exploded=True).save(out / 'EXPLODED.png')
            angles = np.zeros(4)
            for tick,row in enumerate(rows):
                angles = (angles+np.array([row[f'rpm_{i+1}'] for i in range(4)])*2*np.pi/60/config['physics_hz']*model['rotor_spin_signs'])%(2*np.pi)
                if tick % (config['physics_hz']//config['render_hz']):
                    continue
                frame = world.camera(recorded=row,angles=angles)
                draw = ImageDraw.Draw(frame)
                draw.rectangle((0,0,frame.width,config['camera']['header_px']), fill=(17,27,42))
                draw.text((15,9), f"HS-3G-B | PyBullet simulation | {row['t_s']:05.1f} s | {row['phase'].upper()}", fill='white')
                draw.text((15,27), f"z {row['pos_m_z']:.2f} m   |   current {row['current_a_est']:.2f} A (model)   |   no physical hardware", fill=(145,207,225))
                frames.append(frame.quantize(colors=96))
        if frames:
            frames[0].save(out / 'FLIGHT.gif', save_all=True, append_images=frames[1:], duration=round(1000/config['render_hz']), loop=0, optimize=False)
        return rows
    finally:
        world.close()


def hover_estimate(mass, config):
    table = config['motor_table']['value']
    motor = MotorTable(table, config)
    battery = Battery(config, motor)
    b = config['battery']
    weight = mass * config['gravity_m_s2']
    rpm = float(motor.rpm_at_force(weight/4))
    requested = np.full(4, rpm)
    target_mah = b['capacity_mah']['value'] * b['usable_capacity_fraction']['value']
    seconds = 0.
    min_voltage = b['cells']['value'] * config['acceptance']['min_terminal_cell_v']['value']
    initial_current = battery.load(requested)[1]
    termination = '80_percent_depth_of_discharge'
    while battery.consumed_mah < target_mah:
        voltage, current, available = battery.load(requested)
        if voltage < min_voltage or float(np.sum(motor.force_at_rpm(available))) < weight*(1-1e-9):
            termination = 'voltage_or_available_thrust_limit'
            break
        dt = min(b['hover_step_s']['value'], (target_mah-battery.consumed_mah)*3.6/current)
        battery.advance(current, dt)
        seconds += dt
        if target_mah-battery.consumed_mah < 1e-9:
            break
    result = {'model': 'thrust_table_current_at_required_rpm', 'initial_current_a': initial_current,
              'endurance_min': seconds/60, 'termination': termination,
              'capacity_mah': b['capacity_mah']['value'], 'mass_g': mass*1000,
              'initial_soc': b['initial_soc']['value'], 'min_terminal_voltage_v': min_voltage,
              'target_depth_of_discharge': b['usable_capacity_fraction']['value'],
              'assumptions': b['hover_assumptions']}
    alt = config['alternate_estimate']
    result['alternate_estimate'] = {'source': alt['source'],
                                    'current_a': alt['current_a']['value'],
                                    'endurance_min': alt['endurance_min']['value'],
                                    'capacity_mah': alt['capacity_mah']['value'],
                                    'mass_g': alt['mass_g']['value'],
                                    'difference_current_a': alt['current_a']['value']-initial_current,
                                    'difference_endurance_min': alt['endurance_min']['value']-seconds/60,
                                    'assumptions': alt['note']}
    return result


def assess(rows, model, config, scenario):
    """Recomputable acceptance from actual physics telemetry, not renderer state."""
    a = {key: np.array([row[key] for row in rows], dtype=float) for key in rows[0] if key != 'phase'}
    t = a['t_s']
    pos = np.column_stack([a['pos_m_'+x] for x in 'xyz'])
    target = np.column_stack([a['target_m_'+x] for x in 'xyz'])
    error = np.linalg.norm(pos-target,axis=1)
    airborne = (t > .5)&(t < 25)&(a['contact']==0)
    vel = np.column_stack([a['vel_m_s_'+x] for x in 'xyz'])
    force = np.column_stack([a['force_n_'+x] for x in 'xyz'])
    mass = model['mass_kg'] + scenario.get('extra_mass_g',0)/1000
    residual = np.diff(vel,axis=0)*config['physics_hz'] - force[1:]/mass
    continuous_air = airborne[1:] & airborne[:-1]
    force_rms = float(np.sqrt(np.mean(residual[continuous_air]**2))) if continuous_air.any() else None
    position_residual = np.diff(pos,axis=0)*config['physics_hz'] - vel[1:]
    position_rms = float(np.sqrt(np.mean(position_residual[continuous_air]**2))) if continuous_air.any() else None
    touchdown = np.flatnonzero((t>24)&(a['contact']>0))
    limit = config['acceptance']
    metrics = {'tracking_rms_m': float(np.sqrt(np.mean(error[(t>3)&(t<22)]**2))),
               'hover_error_m': float(np.mean(error[(t>4)&(t<5)])),
               'gust_recovery_error_m': float(np.mean(error[(t>20)&(t<21)])) if t[-1]>21 else None,
               'max_tracking_tilt_deg': float(max(a['tilt_deg'][(t>3)&(t<22)])),
               'landing_speed_m_s': float(np.linalg.norm(vel[max(0,touchdown[0]-1)])) if touchdown.size else None,
               'force_balance_rms_m_s2': force_rms,
               'position_velocity_rms_m_s': position_rms,
               'max_rpm': float(max(a[f'rpm_{i}'].max() for i in range(1,5))),
               'peak_current_a_est': float(a['current_a_est'].max()),
               'consumed_mah_est': float(a['consumed_mah_est'][-1]) if 'consumed_mah_est' in a else float(np.trapezoid(a['current_a_est'],t)/3.6),
               'final_position_m': pos[-1].tolist(),
               'landed_contact': bool(a['contact'][-1]),
               'fault_detected': bool(a['fault_detected'].max()), 'rows': len(rows), 'seconds': float(t[-1])}
    checks = {'finite_state': bool(all(np.isfinite(x).all() for x in a.values())),
              'timebase': bool(np.allclose(np.diff(t),1/config['physics_hz'],atol=1e-9)),
              'position_velocity_consistency': position_rms is not None and position_rms < 0.0001,
              'native_force_balance': force_rms is not None and force_rms < limit['force_balance_rms_m_s2']}
    not_gated = {}
    if 'terminal_voltage_v' in a and 'battery' in config:
        b = config['battery']
        voltage_limit = b['cells']['value'] * limit['min_terminal_cell_v']['value']
        metrics['min_terminal_voltage_v'] = float(a['terminal_voltage_v'].min())
        metrics['energy_wh_est'] = float(np.sum(a['terminal_voltage_v']*a['current_a_est'])/config['physics_hz']/3600)
        checks['terminal_voltage'] = metrics['min_terminal_voltage_v'] >= voltage_limit
        motor = MotorTable(config['motor_table']['value'], config)
        minimum_voltage = min(voltage_limit, metrics['min_terminal_voltage_v'])
        metrics['full_throttle_evaluation_voltage_v'] = minimum_voltage
        metrics['thrust_to_weight_at_min_voltage'] = float(4*motor.force_at_rpm(motor.max_rpm*minimum_voltage/b['bench_voltage_v']['value'])/(mass*config['gravity_m_s2']))
        checks['minimum_thrust_to_weight'] = metrics['thrust_to_weight_at_min_voltage'] >= limit['min_thrust_to_weight']['value']
        rated_c = b['c_continuous']['value']
        if rated_c is None:
            not_gated['continuous_current'] = 'no rated C in source data'
        else:
            metrics['rated_continuous_current_a'] = rated_c*b['capacity_mah']['value']/1000
            checks['continuous_current'] = metrics['peak_current_a_est'] <= metrics['rated_continuous_current_a']
        hover = hover_estimate(mass, config)
        metrics['estimated_hover_endurance_min'] = hover['endurance_min']
        requirements = config.get('requirements', {})
        if 'min_hover_endurance_min' in requirements:
            checks['hover_endurance'] = hover['endurance_min'] >= requirements['min_hover_endurance_min']
        else:
            not_gated['hover_endurance'] = 'no endurance requirement declared'
        if 'min_thrust_to_weight' in requirements:
            checks['required_thrust_to_weight'] = metrics['thrust_to_weight_at_min_voltage'] >= requirements['min_thrust_to_weight']
    else:
        hover = None
        checks['battery_telemetry_available'] = False
        not_gated['battery'] = 'not_evaluated: legacy contract or telemetry lacks battery model'
    if scenario['expected'] == 'controlled_landing':
        for key in ['tracking_rms_m','hover_error_m','gust_recovery_error_m','max_tracking_tilt_deg','landing_speed_m_s']:
            checks[key] = metrics[key] is not None and metrics[key] < limit[key]
        yaw_error = np.abs(np.arctan2(np.sin(a['yaw_rad']-a['target_yaw_rad']), np.cos(a['yaw_rad']-a['target_yaw_rad'])))
        metrics['yaw_error_at_hold_deg'] = float(np.degrees(yaw_error[(t>19)&(t<21)].mean()))
        checks['yaw_tracking'] = metrics['yaw_error_at_hold_deg'] < 5
        checks['controlled_ground_contact'] = metrics['landed_contact'] and not metrics['fault_detected']
    else:
        fail = scenario['motor_failure']
        checks['injected_motor_stopped'] = bool(np.all(a[f'rpm_{fail["index"]+1}'][t>fail['at_s']+.1] == 0))
        checks['loss_of_control_observed'] = metrics['fault_detected'] and float(error[t>fail['at_s']].max()) > .3
        checks['failure_reached_ground'] = metrics['landed_contact']
    return {'scenario': scenario, 'metrics': metrics, 'checks': checks, 'accepted': all(checks.values()),
            'hover_estimate': hover, 'not_gated': not_gated}


def freefall_oracle(model, table, config):
    """Independent analytic gravity comparison on the same native rigid body."""
    world = World(model, table, config, {'id':'gravity_oracle'})
    try:
        p = world.p
        p.resetBasePositionAndOrientation(world.body,[0,0,1],[0,0,0,1],physicsClientId=world.client)
        n = 60
        for _ in range(n):
            p.stepSimulation(physicsClientId=world.client)
        pos,_,vel,_,_ = world.state()
        expected_z = 1-config['gravity_m_s2']*world.dt**2*n*(n+1)/2
        expected_vz = -config['gravity_m_s2']*world.dt*n
        return {'engine':'PyBullet DIRECT', 'api_version':p.getAPIVersion(), 'steps':n,
                'zero_motor_thrust':True, 'expected_z_m':expected_z, 'actual_z_m':float(pos[2]),
                'expected_vz_m_s':expected_vz, 'actual_vz_m_s':float(vel[2]),
                'accepted':bool(abs(pos[2]-expected_z)<1e-7 and abs(vel[2]-expected_vz)<1e-7)}
    finally:
        world.close()
