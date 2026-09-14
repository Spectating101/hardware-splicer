`timescale 1ns/1ps

// Hardware Splicer Derived Virtual Lab v1
//
// This is a deliberately bounded, source-derived development model. It is NOT the Winbond
// W25Q128JW vendor Verilog model and is ineligible for vendor-model campaign credit.
// It implements only a read-only 0x9F JEDEC-ID transaction. Other commands produce no data
// response and no modeled flash-state mutation.
module hs_w25q_readonly_reference (
    input  wire cs_n,
    input  wire sclk,
    input  wire mosi,
    output reg  miso
);
    reg [7:0] command_shift;
    reg [3:0] command_bits;
    reg       command_complete;
    reg       jedec_read_mode;
    reg [23:0] response_shift;
    reg [5:0] response_bits_remaining;

    initial begin
        miso = 1'b0;
        command_shift = 8'h00;
        command_bits = 4'd0;
        command_complete = 1'b0;
        jedec_read_mode = 1'b0;
        response_shift = 24'hEF6018;
        response_bits_remaining = 6'd0;
    end

    always @(negedge cs_n) begin
        miso <= 1'b0;
        command_shift <= 8'h00;
        command_bits <= 4'd0;
        command_complete <= 1'b0;
        jedec_read_mode <= 1'b0;
        response_shift <= 24'hEF6018;
        response_bits_remaining <= 6'd0;
    end

    always @(posedge cs_n) begin
        miso <= 1'b0;
        jedec_read_mode <= 1'b0;
        response_bits_remaining <= 6'd0;
    end

    // Mode-0 style command capture: input is sampled on rising edges.
    always @(posedge sclk) begin
        if (!cs_n && !command_complete) begin
            command_shift <= {command_shift[6:0], mosi};
            if (command_bits == 4'd7) begin
                command_complete <= 1'b1;
                command_bits <= 4'd0;
                if ({command_shift[6:0], mosi} == 8'h9F) begin
                    jedec_read_mode <= 1'b1;
                    response_shift <= 24'hEF6018;
                    response_bits_remaining <= 6'd24;
                end else begin
                    jedec_read_mode <= 1'b0;
                    response_bits_remaining <= 6'd0;
                end
            end else begin
                command_bits <= command_bits + 1'b1;
            end
        end
    end

    // Output changes on falling edges so it is stable for the following rising-edge sample.
    always @(negedge sclk) begin
        if (!cs_n && jedec_read_mode && response_bits_remaining != 0) begin
            miso <= response_shift[23];
            response_shift <= {response_shift[22:0], 1'b0};
            response_bits_remaining <= response_bits_remaining - 1'b1;
        end else begin
            miso <= 1'b0;
        end
    end
endmodule
